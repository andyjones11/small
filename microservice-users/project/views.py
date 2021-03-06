import typing
import logging

import bcrypt
from apistar import annotate, Response
from apistar.backends.sqlalchemy_backend import Session
from apistar.interfaces import Auth
from apistar.types import Settings
from apistar_jwt.token import JWT
from apistar_jwt.authentication import JWTAuthentication
from sqlalchemy import exc, or_

from .models import User
from .types import UserType, IdType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


RESPONSE_OBJECT_TEMPLATE = dict()


def list_users_view(session: Session) -> typing.List[UserType]:
    """List all the users in the database."""
    response_object = RESPONSE_OBJECT_TEMPLATE
    queryset = session.query(User).order_by(User.created_at.desc()).all()
    response_object['data'] = {}
    response_object['data']['users'] = [UserType(record) for record in queryset]

    return response_object


def create_user_view(session: Session, user: UserType) -> Response:
    """Create a new user with a given username and password."""
    response_object = RESPONSE_OBJECT_TEMPLATE

    username = user.get('username')
    email = user.get('email')
    password = user.get('password').encode('utf8')

    try:
        user = session.query(User).filter(or_(User.username == username, User.email == email)).first()
        if not user:
            user = User(username=username,
                        email=email,
                        password=password)
            session.add(user)
            session.flush()

            # generate a new auth token
            response_object['message'] = 'Successfully registered.'

            return Response(response_object, status=201)
        else:
            response_object['message'] = 'Sorry, that user already exists'

            return Response(response_object, status=400)

    except (exc.IntegrityError, ValueError) as e:
        session.rollback()
        response_object['message'] = 'Invalid payload'

        return Response(response_object, status=400)


def detail_user_view(session: Session, user_id: IdType) -> Response:
    """Get details about a single user."""
    user = session.query(User).get(user_id)
    response_object = RESPONSE_OBJECT_TEMPLATE

    if not user:
        response_object['message'] = 'User does not exist'
        return Response(response_object, status=204)
    else:
        response_object['data'] = dict(
            id=user.id,
            username=user.username,
            email=user.email
        )
        return response_object


def register_user_view(session: Session, settings: Settings, user: UserType) -> Response:
    """Create a new user with a given username and password."""
    response_object = RESPONSE_OBJECT_TEMPLATE
    SECRET = settings['JWT'].get('SECRET')

    username = user.get('username')
    email = user.get('email')
    password = user.get('password').encode('utf8')
    try:
        user = session.query(User).filter(
            or_(User.username == username, User.email == email)
        ).first()
        if not user:
            user = User(username=username,
                        email=email,
                        password=password)
            session.add(user)
            session.flush()

            payload = dict(email=email)
            new_user_jwt_token = JWT.encode(payload, secret=SECRET)

            # generate a new auth token
            response_object['message'] = 'Successfully registered.'
            response_object['auth_token'] = new_user_jwt_token

            # return Response(response_object, status=201)
            return Response({'auth_token': new_user_jwt_token}, status=201)
        else:
            response_object['message'] = 'Sorry, that user already exists'

            return Response(response_object, status=400)

    except (exc.IntegrityError, ValueError) as e:
        response_object['message'] = 'Invalid payload'

        return Response(response_object, status=400)


def login_user_view(session: Session, settings: Settings, user: UserType) -> Response:
    response_object = RESPONSE_OBJECT_TEMPLATE
    SECRET = settings['JWT'].get('SECRET')

    email = user.get('email')
    password = user.get('password').encode('utf-8')

    try:
        user = session.query(User).filter(User.email == email).first()

        if user and bcrypt.checkpw(password, user.password.encode('utf-8')):
            payload = dict(email=email)
            auth_token = JWT.encode(payload, secret=SECRET)

            if auth_token:
                response_object['status'] = 'success'
                response_object['auth_token'] = auth_token
                return response_object
        else:
            response_object['message'] = 'User does not exist'

            return Response(response_object, status=404)

    except Exception as e:
        response_object['status'] = 'error'
        response_object['message'] = 'Try again.'

        return Response(response_object, status=500)


@annotate(authentication=[JWTAuthentication()])
def logout_user_view(auth: Auth):
    response_object = RESPONSE_OBJECT_TEMPLATE

    if auth.is_authenticated():
        response_object['message'] = 'Successfully logged out.'

        return response_object

    return Response(response_object, 401)


@annotate(authentication=[JWTAuthentication()])
def user_status_view(session: Session, auth: Auth):
    response_object = RESPONSE_OBJECT_TEMPLATE

    if auth.is_authenticated():
        email = auth.user['name']
        user = session.query(User).filter(User.email == email).first()

        if user:
            response_object['data'] = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'active': user.active,
                'created_at': user.created_at.strftime(format='%Y-%m-%d %H:%M')
            }
            return response_object

    response_object['message'] = 'Please provide a valid auth token.'
    return Response(response_object, 401)
