SELECT c.id, c.name, CASE WHEN v.id IS NOT NULL THEN c.email ELSE NULL END AS email
FROM customers c LEFT JOIN emails_verified v ON c.id = v.id
