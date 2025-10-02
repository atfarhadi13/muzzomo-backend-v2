-- Insert Professional records for each user
INSERT INTO professional_professional (
    user_id, license_number, government_issued_id, certification, is_verified, verification_status
)
SELECT
    id,
    'LIC-' || id,
    'driver_license',
    NULL,
    true,
    'approved'
FROM user_customuser;

-- Insert ProfessionalService records for each professional
-- Assign each professional 1-3 services (service IDs 1, 2, 3 for demonstration)
INSERT INTO professional_professionalservice (service_id, professional_id)
SELECT
    s.id AS service_id,
    p.id AS professional_id
FROM professional_professional p
JOIN service_service s ON s.id = ((p.id - 1) % 5) + 1 OR s.id = ((p.id) % 5) + 1
ORDER BY p.id, s.id
LIMIT 3 * (SELECT COUNT(*) FROM professional_professional); -- Each professional gets up to 3 services

-- If you want only one service per professional, use:
-- INSERT INTO professional_professionalservice (service_id, professional_id)
-- SELECT ((p.id - 1) % 5) + 1, p.id FROM professional_professional p;

-- Note: If you have any lines like:
-- INSERT INTO some_table (created_at) VALUES (NOW());
-- Change to:
-- INSERT INTO some_table (created_at) VALUES (CURRENT_TIMESTAMP);
-- INSERT INTO some_table (created_at) VALUES (NOW());
-- Change to:
-- INSERT INTO some_table (created_at) VALUES (CURRENT_TIMESTAMP);
