CREATE TABLE workspace_recovery (
 id INTEGER PRIMARY KEY CHECK(id=1),
 required INTEGER NOT NULL CHECK(required IN (0,1)),
 reason TEXT NOT NULL
);
INSERT INTO workspace_recovery VALUES (1,0,'');
