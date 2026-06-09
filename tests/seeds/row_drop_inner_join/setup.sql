CREATE TABLE events (event_id INT, user_id INT, action TEXT);
INSERT INTO events VALUES (1, 10, 'click'), (2, 20, 'view'), (3, 30, 'click'), (4, 40, 'view'), (5, 50, 'click');
CREATE TABLE active_users (user_id INT);
INSERT INTO active_users VALUES (10), (20), (30)
