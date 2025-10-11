from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound

from .models import Address, City, Province, Country

from .serializers import ( 
    AddressCreateSerializer, 
    AddressUpdateSerializer, 
    AddressReadSerializer,
    CountrySerializer,
    ProvinceSerializer,
    CitySerializer
)

from .permissions import IsOwner

class AddressCreateView(generics.CreateAPIView):
    serializer_class = AddressCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AddressUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        try:
            return Address.objects.filter(user=self.request.user)
        except Exception as e:
            return Address.objects.none()

class AddressListForUserView(generics.ListAPIView):
    serializer_class = AddressReadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        try:
            return (
                Address.objects.filter(user=self.request.user)
                .select_related(
                    "city",
                    "city__province",
                    "city__province__country",
                )
                .order_by("-date_created")
            )
        except Exception as e:
            return Address.objects.none()
        
class CountryListView(APIView):
    def get(self, request):
        countries = Country.objects.all()
        serializer = CountrySerializer(countries, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class CountryDetailView(APIView):
    def get(self, request, pk):
        try:
            country = Country.objects.get(pk=pk)
            serializer = CountrySerializer(country)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Country.DoesNotExist:
            raise NotFound(detail="Country not found")
        
class ProvinceListView(APIView):
    def get(self, request, country_id):
        provinces = Province.objects.filter(country_id=country_id)
        serializer = ProvinceSerializer(provinces, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ProvinceDetailView(APIView):
    def get(self, request, country_id, province_id):
        try:
            province = Province.objects.get(id=province_id, country_id=country_id)
            serializer = ProvinceSerializer(province)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Province.DoesNotExist:
            raise NotFound(detail="Province not found")
        
class CityListView(APIView):
    def get(self, request, country_id, province_id):
        cities = City.objects.filter(province_id=province_id)
        serializer = CitySerializer(cities, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class CityDetailView(APIView):
    def get(self, request, country_id, province_id, city_id):
        try:
            city = City.objects.get(id=city_id, province_id=province_id)
            serializer = CitySerializer(city)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except City.DoesNotExist:
            raise NotFound(detail="City not found")