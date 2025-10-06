INSERT INTO professional_professional (
    user_id, 
    license_number, 
    government_issued_id,
    verification_status,
    is_verified
)
SELECT 
    id AS user_id,
    'LIC' || printf('%06d', id) AS license_number,
    'driver_license' AS government_issued_id,
    'pending' AS verification_status,
    0 AS is_verified
FROM user_customuser 
WHERE (id % 2) = 0;

INSERT INTO professional_professionalservice (service_id, professional_id)
SELECT
    ((p.id - 1) % (SELECT MAX(id) FROM service_service)) + 1 AS service_id,
    p.id AS professional_id
FROM professional_professional p
JOIN user_customuser u ON u.id = p.user_id
WHERE (u.id % 2) = 0;

INSERT INTO professional_professionalservice (service_id, professional_id)
SELECT
    ((p.id) % (SELECT MAX(id) FROM service_service)) + 1 AS service_id,
    p.id AS professional_id
FROM professional_professional p
JOIN user_customuser u ON u.id = p.user_id
WHERE (u.id % 2) = 0
AND NOT EXISTS (
    SELECT 1 
    FROM professional_professionalservice ps 
    WHERE ps.professional_id = p.id 
    AND ps.service_id = ((p.id) % (SELECT MAX(id) FROM service_service)) + 1
);

