INSERT INTO user_customuser (
    email, first_name, last_name, phone_number, is_provider, is_professional, is_verified, is_active, is_staff, is_superuser, date_joined, password
) VALUES
('alice1@example.com', 'Alice', 'Smith', '+12345678901', true, false, true, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('bob2@example.com', 'Bob', 'Johnson', '+12345678902', false, true, false, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('carol3@example.com', 'Carol', 'Williams', '+12345678903', true, true, true, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('dave4@example.com', 'Dave', 'Brown', '+12345678904', false, false, false, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('eve5@example.com', 'Eve', 'Jones', '+12345678905', true, false, true, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('frank6@example.com', 'Frank', 'Garcia', '+12345678906', false, true, false, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('grace7@example.com', 'Grace', 'Martinez', '+12345678907', true, true, true, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('heidi8@example.com', 'Heidi', 'Rodriguez', '+12345678908', false, false, false, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('ivan9@example.com', 'Ivan', 'Lee', '+12345678909', true, false, true, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('judy10@example.com', 'Judy', 'Walker', '+12345678910', false, true, false, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('ken11@example.com', 'Ken', 'Hall', '+12345678911', true, true, true, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('laura12@example.com', 'Laura', 'Allen', '+12345678912', false, false, false, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('mike13@example.com', 'Mike', 'Young', '+12345678913', true, false, true, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('nina14@example.com', 'Nina', 'Hernandez', '+12345678914', false, true, false, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('oscar15@example.com', 'Oscar', 'King', '+12345678915', true, true, true, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('pat16@example.com', 'Pat', 'Wright', '+12345678916', false, false, false, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('quinn17@example.com', 'Quinn', 'Lopez', '+12345678917', true, false, true, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...'),
('ruth18@example.com', 'Ruth', 'Hill', '+12345678918', false, true, false, true, false, false, CURRENT_TIMESTAMP, 'pbkdf2_sha256$...');
