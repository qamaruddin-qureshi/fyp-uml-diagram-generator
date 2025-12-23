from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
import datetime
from flask_login import UserMixin
import uuid



Base = declarative_base()




class User(Base, UserMixin):
    __tablename__ = 'users'
    userid = Column(String(36), primary_key=True, unique=True, nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    passwordhash = Column(String(255), nullable=False)
    createdat = Column(DateTime, default=datetime.datetime.utcnow)
    projects = relationship('Project', back_populates='user')
    stories = relationship('UserStory', back_populates='user')

    def __init__(self, userid=None, username=None, passwordhash=None):
        if userid is not None:
            self.userid = userid
        else:
            self.userid = str(uuid.uuid4())
        if username is not None:
            self.username = username
        if passwordhash is not None:
            self.passwordhash = passwordhash

    # UserMixin requires get_id() method for Flask-Login compatibility
    @property
    def id(self):
        return self.userid
    
    def get_id(self):
        return self.userid





class Project(Base):
    __tablename__ = 'projects'
    projectid = Column(String(36), primary_key=True, unique=True, nullable=False)
    projectname = Column(String(255), nullable=False)
    userid = Column(String(36), ForeignKey('users.userid'), nullable=True)
    user_narration = Column(String, nullable=True)
    createdat = Column(DateTime, default=datetime.datetime.utcnow)
    user = relationship('User', back_populates='projects')
    stories = relationship('UserStory', back_populates='project')
    elements = relationship('ModelElement', back_populates='project')
    
    def __init__(self, projectid=None, projectname=None, userid=None, user_narration=None):
        if projectid is not None:
            self.projectid = projectid
        else:
            self.projectid = str(uuid.uuid4())
        if projectname is not None:
            self.projectname = projectname
        if userid is not None:
            self.userid = userid
        if user_narration is not None:
            self.user_narration = user_narration





class UserStory(Base):
    __tablename__ = 'userstories'
    storyid = Column(String(36), primary_key=True, unique=True, nullable=False)
    projectid = Column(String(36), ForeignKey('projects.projectid'), nullable=False)
    userid = Column(String(36), ForeignKey('users.userid'), nullable=True)
    storytext = Column(String, nullable=False)
    createdat = Column(DateTime, default=datetime.datetime.utcnow)
    project = relationship('Project', back_populates='stories')
    user = relationship('User', back_populates='stories')
    
    def __init__(self, storyid=None, projectid=None, storytext=None):
        if storyid is not None:
            self.storyid = storyid
        else:
            self.storyid = str(uuid.uuid4())
        if projectid is not None:
            self.projectid = projectid
        if storytext is not None:
            self.storytext = storytext





class ModelElement(Base):
    __tablename__ = 'modelelements'
    elementid = Column(String(36), primary_key=True, unique=True, nullable=False)
    projectid = Column(String(36), ForeignKey('projects.projectid'), nullable=False)
    elementtype = Column(String(50), nullable=False)
    elementdata = Column(String, nullable=False)
    sourcestoryid = Column(String(36), ForeignKey('userstories.storyid'), nullable=True)
    createdat = Column(DateTime, default=datetime.datetime.utcnow)
    project = relationship('Project', back_populates='elements')
    
    def __init__(self, elementid=None, projectid=None, elementtype=None, elementdata=None):
        if elementid is not None:
            self.elementid = elementid
        else:
            self.elementid = str(uuid.uuid4())
        if projectid is not None:
            self.projectid = projectid
        if elementtype is not None:
            self.elementtype = elementtype
        if elementdata is not None:
            self.elementdata = elementdata
