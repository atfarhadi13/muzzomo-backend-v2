-- ServiceCategory
INSERT INTO service_servicecategory (title, description, created_at)
VALUES
('Plumbing', 'All plumbing services', CURRENT_TIMESTAMP),
('Electrical', 'Electrical installations and repairs', CURRENT_TIMESTAMP),
('Cleaning', 'Home and office cleaning', CURRENT_TIMESTAMP),
('Gardening', 'Garden maintenance and landscaping', CURRENT_TIMESTAMP),
('Moving', 'Moving and relocation services', CURRENT_TIMESTAMP);

-- Unit
INSERT INTO service_unit (name, code, created_at)
VALUES
('Hour', 'HR', CURRENT_TIMESTAMP),
('Job', 'JB', CURRENT_TIMESTAMP),
('Square Foot', 'SF', CURRENT_TIMESTAMP),
('Visit', 'VS', CURRENT_TIMESTAMP),
('Item', 'IT', CURRENT_TIMESTAMP);

-- Service (assuming category and unit IDs start at 1)
INSERT INTO service_service (title, description, is_trade_required, price, unit_id, created_at)
VALUES
('Basic Plumbing', 'Fix leaks and install faucets', TRUE, 80.00, 1, CURRENT_TIMESTAMP),
('Electrical Wiring', 'Install new wiring', TRUE, 120.00, 1, CURRENT_TIMESTAMP),
('Deep Cleaning', 'Thorough cleaning of all rooms', FALSE, 150.00, 2, CURRENT_TIMESTAMP),
('Lawn Mowing', 'Mow and edge your lawn', FALSE, 50.00, 3, CURRENT_TIMESTAMP),
('Furniture Moving', 'Move furniture within your home', FALSE, 100.00, 2, CURRENT_TIMESTAMP);

-- ServiceType (assuming service IDs start at 1)
INSERT INTO service_servicetype (service_id, title, description, price, created_at)
VALUES
(1, 'Leak Repair', 'Repair leaking pipes', 60.00, CURRENT_TIMESTAMP),
(1, 'Faucet Installation', 'Install new faucet', 90.00, CURRENT_TIMESTAMP),
(2, 'Light Fixture Install', 'Install light fixtures', 70.00, CURRENT_TIMESTAMP),
(2, 'Outlet Replacement', 'Replace electrical outlets', 50.00, CURRENT_TIMESTAMP),
(3, 'Kitchen Cleaning', 'Deep clean kitchen', 60.00, CURRENT_TIMESTAMP);

-- ServicePhoto (assuming service IDs start at 1)
INSERT INTO service_servicephoto (service_id, photo, caption, uploaded_at)
VALUES
(1, 'service_photos/plumbing1.jpg', 'Pipe repair', CURRENT_TIMESTAMP),
(2, 'service_photos/electrical1.jpg', 'Wiring job', CURRENT_TIMESTAMP),
(3, 'service_photos/cleaning1.jpg', 'Clean living room', CURRENT_TIMESTAMP),
(4, 'service_photos/gardening1.jpg', 'Freshly mowed lawn', CURRENT_TIMESTAMP),
(5, 'service_photos/moving1.jpg', 'Moving furniture', CURRENT_TIMESTAMP);

-- ServiceTypePhoto (assuming service_type IDs start at 1)
INSERT INTO service_servicetypephoto (service_type_id, photo, caption, uploaded_at)
VALUES
(1, 'service_type_photos/leakrepair.jpg', 'Leaking pipe', CURRENT_TIMESTAMP),
(2, 'service_type_photos/faucetinstall.jpg', 'Installed faucet', CURRENT_TIMESTAMP),
(3, 'service_type_photos/lightfixture.jpg', 'Light fixture', CURRENT_TIMESTAMP),
(4, 'service_type_photos/outletreplace.jpg', 'Outlet replaced', CURRENT_TIMESTAMP),
(5, 'service_type_photos/kitchenclean.jpg', 'Clean kitchen', CURRENT_TIMESTAMP);

-- Rating (assuming service IDs start at 1 and user_id 1 exists)
INSERT INTO service_rating (service_id, user_id, rating, review, created_at)
VALUES
(1, 1, 5, 'Excellent plumbing service!', CURRENT_TIMESTAMP),
(2, 1, 4, 'Good electrical work.', CURRENT_TIMESTAMP),
(3, 1, 5, 'Spotless cleaning!', CURRENT_TIMESTAMP),
(4, 1, 3, 'Lawn could be better.', CURRENT_TIMESTAMP),
(5, 1, 4, 'Furniture moved safely.', CURRENT_TIMESTAMP);
