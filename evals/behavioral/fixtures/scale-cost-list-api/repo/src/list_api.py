def list_projects(db):
    projects = db.query("SELECT id, name, created_at FROM projects ORDER BY created_at DESC")
    for project in projects:
        rows = db.query(
            "SELECT COUNT(*) AS count FROM tasks WHERE project_id = ?",
            [project["id"]],
        )
        project["task_count"] = rows[0]["count"]
    return projects
