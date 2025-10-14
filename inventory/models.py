from decimal import Decimal
from django.db import models, transaction
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

from professional.models import Professional
from project_management.models import Task


PLAN_LIMITS = {
    "free": {
        "inventory_enabled": False,
        "max_items": 0,
        "max_locations_per_item": 0,
    },
    "pro": {
        "inventory_enabled": True,
        "max_items": 500,
        "max_locations_per_item": 50,
    },
    "enterprise": {
        "inventory_enabled": True,
        "max_items": None,
        "max_locations_per_item": None,
    },
}


def _get_user_plan_limits(user):
    now = timezone.now()
    sub = getattr(user, "professional_subscription", None)
    if not sub or not sub.active or (sub.end_date and sub.end_date <= now):
        return PLAN_LIMITS["free"], "free"
    plan_name = (sub.plan.name if sub.plan else "free").lower()
    limits = PLAN_LIMITS.get(plan_name)
    if not limits:
        limits = {"inventory_enabled": True, "max_items": None, "max_locations_per_item": None}
    return limits, plan_name


def _ensure_inventory_access(user):
    limits, _ = _get_user_plan_limits(user)
    if not limits.get("inventory_enabled", False):
        raise ValidationError("Inventory features require a paid plan.")


def _ensure_item_limit(professional, creating=False):
    limits, _ = _get_user_plan_limits(professional.user)
    if not limits.get("inventory_enabled", False):
        raise ValidationError("Inventory features require a paid plan.")
    cap = limits.get("max_items")
    if cap is None:
        return
    count = InventoryItem.objects.filter(professional=professional).count()
    if creating:
        count += 1
    if count > cap:
        raise ValidationError(f"Plan limit reached: maximum {cap} inventory items.")


def _ensure_location_limit(item, creating=False):
    limits, _ = _get_user_plan_limits(item.professional.user)
    if not limits.get("inventory_enabled", False):
        raise ValidationError("Inventory features require a paid plan.")
    cap = limits.get("max_locations_per_item")
    if cap is None:
        return
    count = ItemLocation.objects.filter(item=item).count()
    if creating:
        count += 1
    if count > cap:
        raise ValidationError(f"Plan limit reached: maximum {cap} locations per item.")


class InventoryItem(models.Model):
    class ItemType(models.TextChoices):
        CONSUMABLE = "consumable", "Consumable"
        REUSABLE = "reusable", "Reusable"

    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name="inventory_items")
    name = models.CharField(max_length=200)
    item_type = models.CharField(max_length=20, choices=ItemType.choices, default=ItemType.CONSUMABLE)
    unit = models.CharField(max_length=20, default="pcs")
    total_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))])
    in_use_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))])
    reorder_point = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))])
    notes = models.CharField(max_length=255, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("professional", "name")]
        ordering = ["name"]
        indexes = [
            models.Index(fields=["professional", "name"]),
            models.Index(fields=["item_type"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(total_quantity__gte=0), name="chk_item_total_qty_gte_zero"),
            models.CheckConstraint(check=models.Q(in_use_quantity__gte=0), name="chk_item_inuse_qty_gte_zero"),
        ]

    def __str__(self):
        return f"{self.name} ({self.item_type})"

    @property
    def available_quantity(self):
        if self.item_type == self.ItemType.CONSUMABLE:
            return self.total_quantity
        return self.total_quantity - self.in_use_quantity

    def clean(self):
        _ensure_inventory_access(self.professional.user)
        if self.item_type == self.ItemType.CONSUMABLE and self.in_use_quantity != 0:
            raise ValidationError("Consumable items cannot have in-use quantity.")
        if self.item_type == self.ItemType.REUSABLE and self.in_use_quantity > self.total_quantity:
            raise ValidationError("In-use quantity cannot exceed total quantity.")
        if self.pk is None:
            _ensure_item_limit(self.professional, creating=True)

    @transaction.atomic
    def add_stock(self, quantity: Decimal, note: str = "", task: Task | None = None):
        _ensure_inventory_access(self.professional.user)
        if quantity <= 0:
            raise ValidationError("Quantity must be positive.")
        self.total_quantity = self.total_quantity + Decimal(quantity)
        self.full_clean()
        self.save(update_fields=["total_quantity", "updated_at"])
        InventoryLog.objects.create(
            professional=self.professional, item=self, action=InventoryLog.Action.ADD,
            quantity=quantity, unit=self.unit, note=note, task=task
        )

    @transaction.atomic
    def consume(self, quantity: Decimal, note: str = "", task: Task | None = None):
        _ensure_inventory_access(self.professional.user)
        if self.item_type != self.ItemType.CONSUMABLE:
            raise ValidationError("Only consumable items can be consumed.")
        if quantity <= 0:
            raise ValidationError("Quantity must be positive.")
        if self.total_quantity < quantity:
            raise ValidationError("Insufficient quantity to consume.")
        self.total_quantity = self.total_quantity - Decimal(quantity)
        self.full_clean()
        self.save(update_fields=["total_quantity", "updated_at"])
        InventoryLog.objects.create(
            professional=self.professional, item=self, action=InventoryLog.Action.CONSUME,
            quantity=quantity, unit=self.unit, note=note, task=task
        )

    @transaction.atomic
    def checkout(self, quantity: Decimal, note: str = "", task: Task | None = None):
        _ensure_inventory_access(self.professional.user)
        if self.item_type != self.ItemType.REUSABLE:
            raise ValidationError("Only reusable items can be checked out.")
        if quantity <= 0:
            raise ValidationError("Quantity must be positive.")
        if self.available_quantity < quantity:
            raise ValidationError("Insufficient available quantity to check out.")
        self.in_use_quantity = self.in_use_quantity + Decimal(quantity)
        self.full_clean()
        self.save(update_fields=["in_use_quantity", "updated_at"])
        InventoryLog.objects.create(
            professional=self.professional, item=self, action=InventoryLog.Action.CHECKOUT,
            quantity=quantity, unit=self.unit, note=note, task=task
        )

    @transaction.atomic
    def checkin(self, quantity: Decimal, note: str = "", task: Task | None = None):
        _ensure_inventory_access(self.professional.user)
        if self.item_type != self.ItemType.REUSABLE:
            raise ValidationError("Only reusable items can be checked in.")
        if quantity <= 0:
            raise ValidationError("Quantity must be positive.")
        if self.in_use_quantity < quantity:
            raise ValidationError("Cannot check in more than in-use.")
        self.in_use_quantity = self.in_use_quantity - Decimal(quantity)
        self.full_clean()
        self.save(update_fields=["in_use_quantity", "updated_at"])
        InventoryLog.objects.create(
            professional=self.professional, item=self, action=InventoryLog.Action.CHECKIN,
            quantity=quantity, unit=self.unit, note=note, task=task
        )

    @transaction.atomic
    def adjust(self, quantity_delta: Decimal, note: str = "", task: Task | None = None):
        _ensure_inventory_access(self.professional.user)
        if quantity_delta == 0:
            return
        new_total = self.total_quantity + Decimal(quantity_delta)
        if new_total < 0:
            raise ValidationError("Adjustment would result in negative total quantity.")
        self.total_quantity = new_total
        self.full_clean()
        self.save(update_fields=["total_quantity", "updated_at"])
        InventoryLog.objects.create(
            professional=self.professional, item=self, action=InventoryLog.Action.ADJUST,
            quantity=quantity_delta, unit=self.unit, note=note, task=task
        )

    @transaction.atomic
    def add_stock_at(self, location: "ItemLocation", quantity: Decimal, note: str = "", task: Task | None = None):
        _ensure_inventory_access(self.professional.user)
        if location.item_id != self.id:
            raise ValidationError("Location does not belong to this item.")
        self.add_stock(quantity, note=note, task=task)
        location.on_hand = location.on_hand + Decimal(quantity)
        location.full_clean()
        location.save(update_fields=["on_hand", "updated_at"])

    @transaction.atomic
    def consume_at(self, location: "ItemLocation", quantity: Decimal, note: str = "", task: Task | None = None):
        _ensure_inventory_access(self.professional.user)
        if location.item_id != self.id:
            raise ValidationError("Location does not belong to this item.")
        self.consume(quantity, note=note, task=task)
        if location.on_hand < quantity:
            raise ValidationError("Insufficient quantity at this location.")
        location.on_hand = location.on_hand - Decimal(quantity)
        location.full_clean()
        location.save(update_fields=["on_hand", "updated_at"])

    @transaction.atomic
    def checkout_at(self, location: "ItemLocation", quantity: Decimal, note: str = "", task: Task | None = None):
        _ensure_inventory_access(self.professional.user)
        if location.item_id != self.id:
            raise ValidationError("Location does not belong to this item.")
        self.checkout(quantity, note=note, task=task)
        if location.on_hand < quantity:
            raise ValidationError("Insufficient available quantity at this location.")
        location.on_hand = location.on_hand - Decimal(quantity)
        location.in_use = location.in_use + Decimal(quantity)
        location.full_clean()
        location.save(update_fields=["on_hand", "in_use", "updated_at"])

    @transaction.atomic
    def checkin_at(self, location: "ItemLocation", quantity: Decimal, note: str = "", task: Task | None = None):
        _ensure_inventory_access(self.professional.user)
        if location.item_id != self.id:
            raise ValidationError("Location does not belong to this item.")
        self.checkin(quantity, note=note, task=task)
        if location.in_use < quantity:
            raise ValidationError("Cannot check in more than in-use at this location.")
        location.in_use = location.in_use - Decimal(quantity)
        location.on_hand = location.on_hand + Decimal(quantity)
        location.full_clean()
        location.save(update_fields=["on_hand", "in_use", "updated_at"])

    @transaction.atomic
    def transfer(self, source: "ItemLocation", dest: "ItemLocation", quantity: Decimal, note: str = ""):
        _ensure_inventory_access(self.professional.user)
        if source.item_id != self.id or dest.item_id != self.id:
            raise ValidationError("Both locations must belong to this item.")
        if quantity <= 0:
            raise ValidationError("Quantity must be positive.")
        if source.on_hand < quantity:
            raise ValidationError("Insufficient quantity at source for transfer.")
        source.on_hand = source.on_hand - Decimal(quantity)
        dest.on_hand = dest.on_hand + Decimal(quantity)
        source.full_clean(); dest.full_clean()
        source.save(update_fields=["on_hand", "updated_at"]); dest.save(update_fields=["on_hand", "updated_at"])
        InventoryLog.objects.create(
            professional=self.professional, item=self, action=InventoryLog.Action.ADJUST,
            quantity=Decimal("0"), unit=self.unit, note=note or f"Transfer {quantity} from {source.location_name} to {dest.location_name}"
        )


class ItemLocation(models.Model):
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name="item_locations")
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="locations")
    location_name = models.CharField(max_length=120)
    on_hand = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))])
    in_use = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("item", "location_name")]
        ordering = ["location_name"]
        indexes = [
            models.Index(fields=["professional", "location_name"]),
            models.Index(fields=["item"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(on_hand__gte=0), name="chk_itemloc_onhand_gte_zero"),
            models.CheckConstraint(check=models.Q(in_use__gte=0), name="chk_itemloc_inuse_gte_zero"),
        ]

    def __str__(self):
        return f"{self.item.name} @ {self.location_name}"

    def clean(self):
        _ensure_inventory_access(self.professional.user)
        if self.item.professional_id != self.professional_id:
            raise ValidationError("Item and location must belong to the same professional.")
        if self.item.item_type == InventoryItem.ItemType.CONSUMABLE and self.in_use != 0:
            raise ValidationError("Consumable items cannot have in-use quantity at a location.")
        if self.pk is None:
            _ensure_location_limit(self.item, creating=True)


class InventoryLog(models.Model):
    class Action(models.TextChoices):
        ADD = "add", "Add"
        CONSUME = "consume", "Consume"
        CHECKOUT = "checkout", "Checkout"
        CHECKIN = "checkin", "Check-in"
        ADJUST = "adjust", "Adjust"

    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name="inventory_logs")
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="logs")
    action = models.CharField(max_length=20, choices=Action.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=20)
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name="inventory_logs")
    note = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["professional", "created_at"]),
            models.Index(fields=["item", "action"]),
            models.Index(fields=["task"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} {self.quantity} {self.unit} · {self.item.name}"

    def clean(self):
        _ensure_inventory_access(self.professional.user)
        if self.item.professional_id != self.professional_id:
            raise ValidationError("Item must belong to the same professional.")
        if self.task and self.task.project.owner_id != self.professional_id:
            raise ValidationError("Task must belong to the same professional (via project owner).")
        if self.action in {self.Action.CONSUME, self.Action.CHECKOUT, self.Action.CHECKIN} and self.quantity <= 0:
            raise ValidationError("Quantity must be positive for this action.")