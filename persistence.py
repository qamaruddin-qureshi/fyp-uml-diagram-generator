
import json
from sqlalchemy import text
from sqlalchemy import create_engine
import logging
import os

# --- SQLAlchemy PostgreSQL Setup ---
POSTGRES_USER = os.environ.get('DB_USER', 'docker')
POSTGRES_PASSWORD = os.environ.get('DB_PASSWORD', 'docker')
POSTGRES_DB = os.environ.get('DB_NAME', 'postgres')
POSTGRES_HOST = os.environ.get('DB_HOST', 'localhost')
POSTGRES_PORT = os.environ.get('DB_PORT', '5432')

SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PersistenceLayer:
    def create_user(self, username, password_hash):
        import uuid
        try:
            result = self.connection.execute(text("SELECT userid FROM users WHERE username = :uname"), {"uname": username})
            if result.first():
                return None
            new_userid = str(uuid.uuid4())
            self.connection.execute(text("INSERT INTO users (userid, username, passwordhash) VALUES (:uid, :uname, :phash)"), {"uid": new_userid, "uname": username, "phash": password_hash})
            self.connection.commit()
            return new_userid
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Create user error: {e}")
            return None

    def get_user_by_username(self, username):
        try:
            result = self.connection.execute(text("SELECT userid, username, passwordhash FROM users WHERE username = :uname"), {"uname": username})
            row = result.first()
            return {'UserID': row[0], 'Username': row[1], 'PasswordHash': row[2]} if row else None
        except Exception as e:
            logger.error(f"Get user error: {e}")
            return None
    def __enter__(self):
        self.connection = engine.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.connection.close()

    def get_all_projects(self):
        try:
            result = self.connection.execute(text("SELECT projectid, projectname, userid FROM projects"))
            projects = []
            for row in result.mappings():
                projects.append({
                    'ProjectID': row['projectid'],
                    'ProjectName': row['projectname'],
                    'UserID': row['userid']
                })
            return projects
        except Exception as e:
            logger.error(f"Get projects error: {e}")
            return []

    def get_project(self, project_id):
        try:
            result = self.connection.execute(text("SELECT projectid, projectname, userid FROM projects WHERE projectid = :pid"), {"pid": project_id})
            row = result.mappings().first()
            if row:
                return {
                    'ProjectID': row['projectid'],
                    'ProjectName': row['projectname'],
                    'UserID': row['userid']
                }
            return None
        except Exception as e:
            logger.error(f"Get project error: {e}")
            return None

    def create_project(self, project_name, user_id=None):
        try:
            import uuid
            project_id = str(uuid.uuid4())
            self.connection.execute(text("INSERT INTO projects (projectid, projectname, userid) VALUES (:pid, :pname, :uid)"), {"pid": project_id, "pname": project_name, "uid": user_id})
            self.connection.commit()
            return project_id
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Create project error: {e}")
            return None

    def get_stories_as_text(self, project_id):
        try:
            result = self.connection.execute(text("SELECT storytext FROM userstories WHERE projectid = :pid ORDER BY storyid"), {"pid": project_id})
            return "\n".join(row[0] for row in result.fetchall())
        except Exception as e:
            logger.error(f"Get stories text error: {e}")
            return ""

    def get_stories_list(self, project_id):
        try:
            result = self.connection.execute(text("SELECT storyid, projectid, storytext FROM userstories WHERE projectid = :pid ORDER BY storyid"), {"pid": project_id})
            return [dict(row) for row in result.mappings().all()]
        except Exception as e:
            logger.error(f"Get stories list error: {e}")
            return []

    def save_stories_from_text(self, project_id, stories_text, user_id=None):
        try:
            import uuid
            self.connection.execute(text("DELETE FROM userstories WHERE projectid = :pid"), {"pid": project_id})
            stories = [story.strip() for story in stories_text.split("\n") if story.strip()]
            for story_text in stories:
                story_id = str(uuid.uuid4())
                self.connection.execute(text("INSERT INTO userstories (storyid, projectid, storytext, userid) VALUES (:sid, :pid, :stext, :uid)"), {"sid": story_id, "pid": project_id, "stext": story_text, "uid": user_id})
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Save stories error: {e}")

    def delete_model_elements(self, project_id):
        try:
            self.connection.execute(text("DELETE FROM modelelements WHERE projectid = :pid"), {"pid": project_id})
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Delete elements error: {e}")

    def save_model_elements(self, project_id, elements):
        try:
            import uuid
            for el in elements:
                element_id = str(uuid.uuid4())
                source_id = el.get('source_id')
                self.connection.execute(text("INSERT INTO modelelements (elementid, projectid, elementtype, elementdata, sourcestoryid) VALUES (:eid, :pid, :etype, :edata, :sid)"), {"eid": element_id, "pid": project_id, "etype": el['type'], "edata": json.dumps(el['data']), "sid": source_id})
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Save elements error: {e}")

    def get_model_elements(self, project_id):
        try:
            result = self.connection.execute(text("SELECT * FROM modelelements WHERE projectid = :pid"), {"pid": project_id})
            return [dict(row) for row in result.mappings().all()]
        except Exception as e:
            logger.error(f"Get model elements error: {e}")
            return []
