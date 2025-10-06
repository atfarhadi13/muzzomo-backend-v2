INSERT INTO address_country (name, code) VALUES ('Canada', 'CA');

INSERT INTO address_province (name, country_id, code) VALUES
('Alberta', (SELECT id FROM address_country WHERE code='CA'), 'AB'),
('British Columbia', (SELECT id FROM address_country WHERE code='CA'), 'BC'),
('Manitoba', (SELECT id FROM address_country WHERE code='CA'), 'MB'),
('New Brunswick', (SELECT id FROM address_country WHERE code='CA'), 'NB'),
('Newfoundland and Labrador', (SELECT id FROM address_country WHERE code='CA'), 'NL'),
('Nova Scotia', (SELECT id FROM address_country WHERE code='CA'), 'NS'),
('Northwest Territories', (SELECT id FROM address_country WHERE code='CA'), 'NT'),
('Nunavut', (SELECT id FROM address_country WHERE code='CA'), 'NU'),
('Ontario', (SELECT id FROM address_country WHERE code='CA'), 'ON'),
('Prince Edward Island', (SELECT id FROM address_country WHERE code='CA'), 'PE'),
('Quebec', (SELECT id FROM address_country WHERE code='CA'), 'QC'),
('Saskatchewan', (SELECT id FROM address_country WHERE code='CA'), 'SK'),
('Yukon', (SELECT id FROM address_country WHERE code='CA'), 'YT');

INSERT INTO address_city (name, province_id) VALUES
('Calgary', (SELECT id FROM address_province WHERE code='AB')),
('Edmonton', (SELECT id FROM address_province WHERE code='AB')),
('Red Deer', (SELECT id FROM address_province WHERE code='AB')),

('Vancouver', (SELECT id FROM address_province WHERE code='BC')),
('Victoria', (SELECT id FROM address_province WHERE code='BC')),
('Kelowna', (SELECT id FROM address_province WHERE code='BC')),

('Winnipeg', (SELECT id FROM address_province WHERE code='MB')),
('Brandon', (SELECT id FROM address_province WHERE code='MB')),
('Steinbach', (SELECT id FROM address_province WHERE code='MB')),

('Moncton', (SELECT id FROM address_province WHERE code='NB')),
('Saint John', (SELECT id FROM address_province WHERE code='NB')),
('Fredericton', (SELECT id FROM address_province WHERE code='NB')),

('St. John''s', (SELECT id FROM address_province WHERE code='NL')),
('Mount Pearl', (SELECT id FROM address_province WHERE code='NL')),
('Corner Brook', (SELECT id FROM address_province WHERE code='NL')),

('Halifax', (SELECT id FROM address_province WHERE code='NS')),
('Sydney', (SELECT id FROM address_province WHERE code='NS')),
('Truro', (SELECT id FROM address_province WHERE code='NS')),

('Yellowknife', (SELECT id FROM address_province WHERE code='NT')),
('Hay River', (SELECT id FROM address_province WHERE code='NT')),
('Inuvik', (SELECT id FROM address_province WHERE code='NT')),

('Iqaluit', (SELECT id FROM address_province WHERE code='NU')),
('Rankin Inlet', (SELECT id FROM address_province WHERE code='NU')),
('Arviat', (SELECT id FROM address_province WHERE code='NU')),

('Toronto', (SELECT id FROM address_province WHERE code='ON')),
('Ottawa', (SELECT id FROM address_province WHERE code='ON')),
('Hamilton', (SELECT id FROM address_province WHERE code='ON')),

('Charlottetown', (SELECT id FROM address_province WHERE code='PE')),
('Summerside', (SELECT id FROM address_province WHERE code='PE')),
('Stratford', (SELECT id FROM address_province WHERE code='PE')),

('Montreal', (SELECT id FROM address_province WHERE code='QC')),
('Quebec City', (SELECT id FROM address_province WHERE code='QC')),
('Laval', (SELECT id FROM address_province WHERE code='QC')),

('Saskatoon', (SELECT id FROM address_province WHERE code='SK')),
('Regina', (SELECT id FROM address_province WHERE code='SK')),
('Prince Albert', (SELECT id FROM address_province WHERE code='SK')),

('Whitehorse', (SELECT id FROM address_province WHERE code='YT')),
('Dawson City', (SELECT id FROM address_province WHERE code='YT')),
('Watson Lake', (SELECT id FROM address_province WHERE code='YT'));

INSERT INTO address_address (
    user_id, street_number, street_name, unit_suite, city_id, postal_code, latitude, longitude, date_created, date_updated
) VALUES
(1, '101', 'Main St', 'A', (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A1', 51.0447, -114.0719, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '102', 'Main St', 'B', (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A2', 51.0448, -114.0720, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '103', 'Main St', NULL, (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A3', 51.0449, -114.0721, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '104', 'Main St', 'C', (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A4', 51.0450, -114.0722, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '105', 'Main St', NULL, (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A5', 51.0451, -114.0723, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '106', 'Main St', 'D', (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A6', 51.0452, -114.0724, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '107', 'Main St', NULL, (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A7', 51.0453, -114.0725, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '108', 'Main St', 'E', (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A8', 51.0454, -114.0726, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '109', 'Main St', NULL, (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A9', 51.0455, -114.0727, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '110', 'Main St', 'F', (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1B0', 51.0456, -114.0728, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT INTO address_address (user_id, street_number, street_name, unit_suite, city_id, postal_code, latitude, longitude, date_created, date_updated) VALUES
(1, '101', 'Main St', 'A', (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A1', 51.0447, -114.0719, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '102', 'Main St', 'B', (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A2', 51.0448, -114.0720, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '103', 'Main St', NULL, (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A3', 51.0449, -114.0721, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '104', 'Main St', 'C', (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A4', 51.0450, -114.0722, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '105', 'Main St', NULL, (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A5', 51.0451, -114.0723, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '106', 'Main St', 'D', (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A6', 51.0452, -114.0724, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '107', 'Main St', NULL, (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A7', 51.0453, -114.0725, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '108', 'Main St', 'E', (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A8', 51.0454, -114.0726, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '109', 'Main St', NULL, (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1A9', 51.0455, -114.0727, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '110', 'Main St', 'F', (SELECT id FROM address_city WHERE name='Calgary'), 'T2P1B0', 51.0456, -114.0728, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT INTO address_address (user_id, street_number, street_name, unit_suite, city_id, postal_code, latitude, longitude, date_created, date_updated) VALUES
(1, '201', 'Jasper Ave', '1A', (SELECT id FROM address_city WHERE name='Edmonton'), 'T5J1N1', 53.5461, -113.4938, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '202', 'Jasper Ave', '2B', (SELECT id FROM address_city WHERE name='Edmonton'), 'T5J1N2', 53.5462, -113.4939, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '203', 'Whyte Ave', NULL, (SELECT id FROM address_city WHERE name='Edmonton'), 'T6E1Z3', 53.5463, -113.4940, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '204', 'Whyte Ave', '3C', (SELECT id FROM address_city WHERE name='Edmonton'), 'T6E1Z4', 53.5464, -113.4941, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '205', 'Whyte Ave', NULL, (SELECT id FROM address_city WHERE name='Edmonton'), 'T6E1Z5', 53.5465, -113.4942, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '206', 'Whyte Ave', '4D', (SELECT id FROM address_city WHERE name='Edmonton'), 'T6E1Z6', 53.5466, -113.4943, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '207', 'Whyte Ave', NULL, (SELECT id FROM address_city WHERE name='Edmonton'), 'T6E1Z7', 53.5467, -113.4944, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '208', 'Whyte Ave', '5E', (SELECT id FROM address_city WHERE name='Edmonton'), 'T6E1Z8', 53.5468, -113.4945, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '209', 'Whyte Ave', NULL, (SELECT id FROM address_city WHERE name='Edmonton'), 'T6E1Z9', 53.5469, -113.4946, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '210', 'Whyte Ave', '6F', (SELECT id FROM address_city WHERE name='Edmonton'), 'T6E1Y0', 53.5470, -113.4947, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT INTO address_address (user_id, street_number, street_name, unit_suite, city_id, postal_code, latitude, longitude, date_created, date_updated) VALUES
(1, '301', 'Ross St', 'A', (SELECT id FROM address_city WHERE name='Red Deer'), 'T4N1A1', 52.2681, -113.8112, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '302', 'Ross St', 'B', (SELECT id FROM address_city WHERE name='Red Deer'), 'T4N1A2', 52.2682, -113.8113, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '303', 'Gaetz Ave', NULL, (SELECT id FROM address_city WHERE name='Red Deer'), 'T4N1A3', 52.2683, -113.8114, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '304', 'Gaetz Ave', 'C', (SELECT id FROM address_city WHERE name='Red Deer'), 'T4N1A4', 52.2684, -113.8115, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '305', 'Gaetz Ave', NULL, (SELECT id FROM address_city WHERE name='Red Deer'), 'T4N1A5', 52.2685, -113.8116, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '306', 'Gaetz Ave', 'D', (SELECT id FROM address_city WHERE name='Red Deer'), 'T4N1A6', 52.2686, -113.8117, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '307', 'Gaetz Ave', NULL, (SELECT id FROM address_city WHERE name='Red Deer'), 'T4N1A7', 52.2687, -113.8118, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '308', 'Gaetz Ave', 'E', (SELECT id FROM address_city WHERE name='Red Deer'), 'T4N1A8', 52.2688, -113.8119, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '309', 'Gaetz Ave', NULL, (SELECT id FROM address_city WHERE name='Red Deer'), 'T4N1A9', 52.2689, -113.8120, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '310', 'Gaetz Ave', 'F', (SELECT id FROM address_city WHERE name='Red Deer'), 'T4N1B0', 52.2690, -113.8121, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT INTO address_address (user_id, street_number, street_name, unit_suite, city_id, postal_code, latitude, longitude, date_created, date_updated) VALUES
(1, '401', 'Granville St', '101', (SELECT id FROM address_city WHERE name='Vancouver'), 'V6Z1A1', 49.2827, -123.1207, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '402', 'Granville St', '102', (SELECT id FROM address_city WHERE name='Vancouver'), 'V6Z1A2', 49.2828, -123.1208, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '403', 'Robson St', NULL, (SELECT id FROM address_city WHERE name='Vancouver'), 'V6Z1A3', 49.2829, -123.1209, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '404', 'Robson St', '103', (SELECT id FROM address_city WHERE name='Vancouver'), 'V6Z1A4', 49.2830, -123.1210, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '405', 'Robson St', NULL, (SELECT id FROM address_city WHERE name='Vancouver'), 'V6Z1A5', 49.2831, -123.1211, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '406', 'Robson St', '104', (SELECT id FROM address_city WHERE name='Vancouver'), 'V6Z1A6', 49.2832, -123.1212, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '407', 'Robson St', NULL, (SELECT id FROM address_city WHERE name='Vancouver'), 'V6Z1A7', 49.2833, -123.1213, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '408', 'Robson St', '105', (SELECT id FROM address_city WHERE name='Vancouver'), 'V6Z1A8', 49.2834, -123.1214, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '409', 'Robson St', NULL, (SELECT id FROM address_city WHERE name='Vancouver'), 'V6Z1A9', 49.2835, -123.1215, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '410', 'Robson St', '106', (SELECT id FROM address_city WHERE name='Vancouver'), 'V6Z1B0', 49.2836, -123.1216, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);


INSERT INTO address_address (user_id, street_number, street_name, unit_suite, city_id, postal_code, latitude, longitude, date_created, date_updated) VALUES
(1, '501', 'Douglas St', '201', (SELECT id FROM address_city WHERE name='Victoria'), 'V8W1A1', 48.4284, -123.3656, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '502', 'Douglas St', '202', (SELECT id FROM address_city WHERE name='Victoria'), 'V8W1A2', 48.4285, -123.3657, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '503', 'Government St', NULL, (SELECT id FROM address_city WHERE name='Victoria'), 'V8W1A3', 48.4286, -123.3658, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '504', 'Government St', '203', (SELECT id FROM address_city WHERE name='Victoria'), 'V8W1A4', 48.4287, -123.3659, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '505', 'Government St', NULL, (SELECT id FROM address_city WHERE name='Victoria'), 'V8W1A5', 48.4288, -123.3660, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '506', 'Government St', '204', (SELECT id FROM address_city WHERE name='Victoria'), 'V8W1A6', 48.4289, -123.3661, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '507', 'Government St', NULL, (SELECT id FROM address_city WHERE name='Victoria'), 'V8W1A7', 48.4290, -123.3662, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '508', 'Government St', '205', (SELECT id FROM address_city WHERE name='Victoria'), 'V8W1A8', 48.4291, -123.3663, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '509', 'Government St', NULL, (SELECT id FROM address_city WHERE name='Victoria'), 'V8W1A9', 48.4292, -123.3664, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '510', 'Government St', '206', (SELECT id FROM address_city WHERE name='Victoria'), 'V8W1B0', 48.4293, -123.3665, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT INTO address_address (user_id, street_number, street_name, unit_suite, city_id, postal_code, latitude, longitude, date_created, date_updated) VALUES
(1, '601', 'Yonge St', '301', (SELECT id FROM address_city WHERE name='Toronto'), 'M4W1A1', 43.6510, -79.3802, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '602', 'Yonge St', '302', (SELECT id FROM address_city WHERE name='Toronto'), 'M4W1A2', 43.6511, -79.3803, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '603', 'Queen St W', NULL, (SELECT id FROM address_city WHERE name='Toronto'), 'M5V2B3', 43.6512, -79.3804, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '604', 'Queen St W', '303', (SELECT id FROM address_city WHERE name='Toronto'), 'M5V2B4', 43.6513, -79.3805, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '605', 'Queen St W', NULL, (SELECT id FROM address_city WHERE name='Toronto'), 'M5V2B5', 43.6514, -79.3806, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '606', 'Queen St W', '304', (SELECT id FROM address_city WHERE name='Toronto'), 'M5V2B6', 43.6515, -79.3807, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '607', 'Queen St W', NULL, (SELECT id FROM address_city WHERE name='Toronto'), 'M5V2B7', 43.6516, -79.3808, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '608', 'Queen St W', '305', (SELECT id FROM address_city WHERE name='Toronto'), 'M5V2B8', 43.6517, -79.3809, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '609', 'Queen St W', NULL, (SELECT id FROM address_city WHERE name='Toronto'), 'M5V2B9', 43.6518, -79.3810, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(1, '610', 'Queen St W', '306', (SELECT id FROM address_city WHERE name='Toronto'), 'M5V2C0', 43.6519, -79.3811, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
