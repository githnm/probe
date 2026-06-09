SELECT e.event_id, e.user_id, e.action
FROM events e INNER JOIN active_users a ON e.user_id = a.user_id
