from sanic import Sanic, SanicException
from sanic.response import text, file, html, json, redirect
from sanic_ext import Extend

from pymongo import MongoClient
from redis import Redis

import gzip
import time

import string
import random

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHash

from functools import partial
from geopy.geocoders import Nominatim
from pymongo import GEO2D

def validate_username(username: str) -> bool:
    if not (4 <= len(username) <= 16):
        return False

    # leading and trailing spaces should be removed
    if username != username.strip():
        raise ValueError("Username cannot have leading or trailing spaces")

    # username must be lowercase
    # while the user can enter anything
    # username should have been converted to lowercase
    if username != username.lower():
        raise ValueError("Username must be lowercase")

    valid_letters = string.ascii_lowercase + string.digits + "_"
    for char in username:
        if char not in valid_letters:
            return False

    # the first character must be a letter
    if not username[0].isalpha():
        return False

    # two or more consecutive underscores are not allowed
    if "__" in username:
        return False

    return True


app = Sanic(__name__)
app.config.OAS = False

Extend(app)

client = MongoClient("mongodb://localhost:27017/")
db = client["taxi"]

rd = Redis(host="localhost", port=6379, db=0)

geolocator = Nominatim(user_agent="taxi")

random_token = lambda: "".join(random.choices(string.ascii_letters, k=32))

REDIS_TESTING = True
MONGO_TESTING = True

# TODO: hash these passwords
SUPER_USERS = [("root", "root")]
SUPER_TOKEN = random_token()

assert len(SUPER_USERS) > 0, "There must be at least one super user"
assert all(
    len(u) == 2 for u in SUPER_USERS
), "Super users must be a list of tuples (username, password)"
assert all(
    type(u[0]) == type(u[1]) == str for u in SUPER_USERS
), "Passwords and usernames must be strings"


@app.middleware("response")
async def compress_response(request, response):
    if len(response.body) and "gzip" in request.headers["Accept-Encoding"]:
        compressed = gzip.compress(response.body)

        response.body = compressed
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Vary"] = "Accept-Encoding"
        response.headers["Content-Length"] = len(compressed)


@app.middleware("request")
async def compress_request(request):
    if "Content-Encoding" in request.headers:
        if request.headers["Content-Encoding"] == "gzip":
            request.body = gzip.decompress(request.body)


# temporary just for development
@app.middleware("response")
async def add_css(request, response):
    if "text/html" in response.content_type:
        response.body += "<link rel='stylesheet' href='/style.css'>".encode()


# @app.exception(SanicException)
# async def manage_exception(request, exception):
#    # exception.args = ("There is something wrong",)
#    # message, = exception.args
#    try:
#       status_code = exception.status_code
#       return text(f"Ops! There was an {status_code} Error", status=status_code)
#    except:


@app.get("/style.css")
async def style(request):
    return await file("style.css")


@app.get("/")
@app.ext.template("main.html")
async def index(request):
    return {"name": "World"}


@app.route("/admin", methods=["GET", "POST"])
@app.ext.template("admin.html")
async def admin(request):
    if request.method == "GET":
        return {"error": None}

    username = request.form.get("username")
    password = request.form.get("password")

    if not username or not password:
        return {"error": "Username and password are required"}

    if (username, password) in SUPER_USERS:
        global SUPER_TOKEN
        SUPER_TOKEN = random_token()

        # TODO: add expiary for the SUPER_TOKEN

        # sudo stands for `SuperUser DO`
        resp = redirect("/sudo")
        resp.add_cookie("token", SUPER_TOKEN)
        return resp

    # if admin is not a superuser
    # check in the database

    hasher = PasswordHasher()

    result = db.admins.find_one({"username": username})

    try:
        hasher.verify(result.get("password"), password)

        token = random_token()
        # the token is only valid for 24 hours
        rd.setex(token, 60 * 60 * 24, username)

        # links based on roles
        resp = "<br>".join(f"<a href='/admin/{i}'>{i}</a>" for i in result.get("roles"))
        resp = html(resp)
        resp.cookies["token"] = token
        return resp
    except VerificationError:
        return {"error": "Invalid username or password"}


@app.get("/admin/<role>")
@app.ext.template("role.html")
async def role(request, role):
    token = request.cookies.get("token")

    user = rd.get(token)
    if not user:
        return redirect("/admin")

    user = user.decode()
    user = db.admins.find_one({"username": user})

    if role not in user.get("roles"):
        return redirect("/admin")

    return {"role": role, "user": user}


# sudo path which allows superusers to add new admins
# and manage their roles
# the roles are:
#   - dev: Developer
#   - mod: Moderator
#   - adm: Administrator
#   - opt: Operator (for manual data entry)
# A user can have one or more roles
@app.route("/sudo", methods=["GET", "POST"])
@app.ext.template("sudo.html")
async def sudo(request):
    token = request.cookies.get("token")

    if token != SUPER_TOKEN:
        # In production, this should be a 404 error
        # raise SanicException("", status_code=404)
        raise SanicException("You are not authorized", status_code=401)

    data = db.admins.find()

    if request.method == "GET":
        return {"data": data, "message": ""}

    username = request.form.get("username").strip().lower()
    password = request.form.get("password")

    roles = request.form.get("roles")

    if not all([username, password, roles]):
        return {"data": data, "message": "All fields are required"}

    roles = roles.strip().lower()
    roles = set([i.strip() for i in roles.split(",")])

    if not roles.issubset({"dev", "mod", "adm", "opt"}):
        invalid_roles = ", ".join(roles - {"dev", "mod", "adm", "opt"})
        return {"data": data, "message": f"Invalid roles: {invalid_roles}"}

    if db.admins.find_one({"username": username}):
        return {"data": data, "message": "Username already exists"}

    # TODO: username check
    # TODO: password strength check

    hasher = PasswordHasher()
    hashed = hasher.hash(password)

    db.admins.insert_one(
        {"username": username, "password": hashed, "roles": list(roles)}
    )

    return {"data": data, "message": "Admin added successfully"}


def send_mail(to, message):
    with open(f"temp/{to}_{random_token()}.txt", "w") as f:
        f.write(f"to: {to}\n")
        f.write(message)

@app.route("quick", methods=["GET", "POST"])
@app.ext.template("quick.html")
async def quick(request):
    if request.method == "GET":
        return {"error": None}
    
    email = request.form.get("email")
    category = request.form.get("category").lower()
    
    if category not in ["driver", "passenger"]:
        return {"error": "Invalid user category"}
    
    username = random_token().lower()
    password = random_token().lower()
    
    hasher = PasswordHasher()
    hashed = hasher.hash(password)
    
    send_mail(email, f'please login with\n\tusername: {username}\n\tpassword: {password}\nto continue')
    
    db.users.insert_one(
        {"username": username, "password": hashed, "category": category, "temp": True}
    )
    
    return text("please check your email")
    

# join path for debugging
# takes username, password (with confirmation) and type
# type can be either "driver" or "passenger"
@app.route("/join", methods=["GET", "POST"])
@app.ext.template("join.html")
async def join(request):
    if request.method == "GET":
        return {"error": None}

    username = request.form.get("username")
    password = request.form.get("password")
    confirm_ = request.form.get("confirm_")
    category = request.form.get("category").lower()

    if not all([username, password, confirm_, category]):
        return {"error": "All fields are required"}

    if password != confirm_:
        return {"error": "Passwords do not match"}

    if category not in ["driver", "passenger"]:
        return {"error": "Invalid user category"}
    
    if db.users.find({"username": username, "temp": False}):
        return "Username already there"
    
    hasher = PasswordHasher()
    hashed = hasher.hash(password)

    db.users.insert_one(
        {"username": username, "password": hashed, "category": category, "temp": False}
    )

    return redirect("/login")


# login with username, password and category
# category can be either "driver" or "passenger"
@app.route("/login", methods=["GET", "POST"])
@app.ext.template("login.html")
async def login(request):
    if request.method == "GET":
        return {"error": None}

    username = request.form.get("username")
    password = request.form.get("password")
    category = request.form.get("category").lower()

    if not all([username, password, category]):
        return {"error": "All fields are required"}

    if category not in ["driver", "passenger"]:
        return {"error": "Invalid user category"}

    hasher = PasswordHasher()
    result = db.users.find_one({"username": username})
    
    if not result:
        return {"error": "Username Not Found"}

    try:
        hasher.verify(result.get("password"), password)

        token = random_token()
        # the token is only valid for 24 hours
        rd.setex(token, 60 * 60 * 24, username)

        if category == "driver":
            resp = redirect("/pick")
        else:
            resp = redirect("/reserve")
        resp.add_cookie("token", token)
        return resp
    except VerificationError:
        return {"error": "Invalid username or password"}
    except InvalidHash:
        # Invalid hashes should never be in the database
        # TODO: log this error with the username
        raise SanicException(None, status_code=500)
    

@app.route("/change")
@app.ext.template("change.html")
async def change(request):
    token = request.cookie.get("token")
    user = rd.get(token)
    
    if not user:
        return redirect("/login")
    
    user = user.decode()
    user = db.users.find_one({"username": user})
    
    username = request.form.get("username")
    password = request.form.get("password")
    confirm_ = request.form.get("confirm_")
    
    if not all([username, password, confirm_]):
        return {"error": "All fields are required"}

    if password != confirm_:
        return {"error": "Passwords do not match"}
    
    hasher = PasswordHasher()
    hashed = hasher.hash(password)
    
    db.users.update_one({"username": user})
    
    
    
@app.route("/users")
async def list_users(request):
    data = []
    for i in db.users.find():
        del i["_id"]
        data.append(dict(i))
        
    return json(data)
    
    
@app.route("/reserve", methods=["GET", "POST"])
@app.ext.template("reserve.html")
async def reserve(request):
    token = request.cookies.get("token")
    user = rd.get(token)
    if not user:
        return redirect("/login")

    user = user.decode()
    user = db.users.find_one({"username": user})
    
    if user.get("category") != "passenger":
        raise SanicException("Only passengers can reserve taxis", status_code=401)
    
    reservations = db.reservations.find({"username": user.get("username")})
    if request.method == "GET":
        return {"error": None, "data": reservations}
    
    curr_adr = request.form.get("curr_adr")
    if not curr_adr:
        curr_lon = request.form.get("curr_lon")
        curr_lat = request.form.get("curr_lat")
        
        if not all([curr_lon, curr_lat]):
            raise SanicException("Current address or location is required", status_code=400)
        
        curr_adr = geolocator.reverse(f"{curr_lat}, {curr_lon}")
        curr_adr = curr_adr.address if curr_adr else None
    else:
        curr_adr = geolocator.geocode(curr_adr)
        if not curr_adr:
            raise SanicException("Invalid current address", status_code=400)
        curr_lon, curr_lat = curr_adr.longitude, curr_adr.latitude
        curr_adr = curr_adr.address
    
    dest_adr = request.form.get("dest_adr")
    if not dest_adr:
        dest_lon = request.form.get("dest_lon")
        dest_lat = request.form.get("dest_lat")
        
        if not all([dest_lon, dest_lat]):
            raise SanicException("Destination address or location is required", status_code=400)
        
        dest_adr = geolocator.reverse(f"{dest_lat}, {dest_lon}")
        dest_adr = dest_adr.address if dest_adr else None
    else:
        dest_adr = geolocator.geocode(dest_adr)
        if not dest_adr:
            raise SanicException("Invalid destination address", status_code=400)
        dest_lon, dest_lat = dest_adr.longitude, dest_adr.latitude
        dest_adr = dest_adr.address
    
    # TODO: allow users to choose a custom depature time
    depature_time = time.time() + 60 * 5
    
    # check if depature time is more than an hour in the past
    if depature_time < time.time() - 60 * 60:
        raise SanicException("Depature time cannot be in the past", status_code=400)
    # or more than 24 hours in the future
    if depature_time > time.time() + 60 * 60 * 24:
        raise SanicException("Depature time cannot be more than 24 hours in the future", status_code=400)
    
    min_rating = request.form.get("min_rating")
    min_rating = float(min_rating) if min_rating else 0.0
    min_rating = min(5.0, max(0.0, min_rating))
    
    # to make querying easier, min_rating is stored as an integer
    # between 0 and 100
    min_rating = int(min_rating * 20)
    
    error = None
    result = db.reservations.delete_one({"username": user.get("username"), "finished": False})
    if result.deleted_count > 0:
        error = "You had an existing reservation; It was automatically cancelled"
    
    db.reservations.insert_one({
        "username": user.get("username"),
        "curr_adr": curr_adr,
        "curr_location": {
            "type": "Point",
            "coordinates": [float(curr_lon), float(curr_lat)]
        },
        "dest_adr": dest_adr,
        "dest_location": {
            "type": "Point",
            "coordinates": [float(dest_lon), float(dest_lat)]
        },
        "depature_time": depature_time,
        "min_rating": min_rating,
        
        "picked": False,
        "picked_driver" : "",
        
        "finished": False
    })
    
    return {"error": error, "data": reservations}


# /pick page for drivers to select passengers
@app.route("/pick", methods=["GET", "POST"])
@app.ext.template("pick.html")
async def pick(request):
    token = request.cookies.get("token")
    user = rd.get(token)
    if not user:
        return redirect("/login")

    user = user.decode()
    user = db.users.find_one({"username": user})
    
    if user.get("category") != "driver":
        raise SanicException("Only drivers can pickup passengers", status_code=401)
    
    # check if driver is busy
    if db.reservations.find_one({"picked_driver": user.get("username"), "finished": False}):
        return redirect("/busy")
    
    reservations = db.reservations.find({"picked": False})
    if request.method == "GET":
        return {"error": None, "data": reservations}
    
    picked = request.form.get("picked") # username of the passenger
    if not picked:
        raise SanicException("Passenger not selected", status_code=400)
        
    # check if the passenger is still available
    reservation = db.reservations.find_one({"username": picked, "picked": False, "finished": False})
    if not reservation:
        raise SanicException("Passenger not available", status_code=400)
        
    # TODO: verify rating
        
    db.reservations.update_one({"username": picked, "finished": False}, {"$set": {"picked": True, "picked_driver": user.get("username")}})
    return redirect("/busy")
    
    
# /busy page for the drivers to remind them that they are busy
# if they are not busy, they should be redirected to /pick
# they should also be given an option to finish the current trip
@app.route("/busy", methods=["GET", "POST"])
async def busy(request):
    token = request.cookies.get("token")
    user = rd.get(token)
    if not user:
        return redirect("/login")

    user = user.decode()
    user = db.users.find_one({"username": user})
    
    if user.get("category") != "driver":
        raise SanicException("Only drivers can pickup passengers", status_code=401)
    
    reservation = db.reservations.find_one({"picked_driver": user.get("username"), "finished": False})
    if not reservation:
        return redirect("/pick")
    
    if request.method == "GET":
        return html(f'''ep ep 1
                    
        <p>You are currently busy with a {reservation['username']}</p>
        <form method="POST" action="/busy">
            <input type="submit" name="finish" value="finish">
        </form>
    ''')
        
    # check if the value is "finish"
    print(request.form)
    if request.form.get("finish") != "finish":
        return redirect("/busy")
    
    db.reservations.update_one({"username": reservation['username'], "finished": False}, {"$set": {"finished": True}})
    return redirect("/pick")
    
    

# only for debug purposes
@app.get("/reservations")
async def list_reservations(request):
    data = db.reservations.find()
    table_html = "<table>"
    table_html += "<tr><th>Username</th><th>Current Address</th><th>Current Location</th><th>Destination Address</th><th>Destination Location</th><th>Departure Time</th><th>Minimum Rating</th></tr>"
    for reservation in data:
        print(reservation)
        table_html += f"<tr><td>{reservation['username']}</td><td>{reservation['curr_adr']}</td><td>{reservation['curr_location']}</td><td>{reservation['dest_adr']}</td><td>{reservation['dest_location']}</td><td>{reservation['depature_time']}</td><td>{reservation['min_rating']}</td></tr>"
    table_html += "</table>"
    return html(table_html)
    
    


str_resp = lambda x: text(str(x))

if REDIS_TESTING:

    @app.get("/get/<key>")
    async def redis_get(request, key):
        return str_resp(rd.get(key))

    @app.get("/set/<key>/<val>")
    async def redis_set(request, key, val):
        return str_resp(rd.set(key, val))

    @app.get("/del/<key>")
    async def redis_delete(request, key):
        return str_resp(rd.delete(key))

    @app.get("/incr/<key>")
    async def redis_incr(request, key):
        return str_resp(rd.incr(key))

    @app.get("/decr/<key>")
    async def redis_decr(request, key):
        return str_resp(rd.decr(key))

    @app.get("/keys")
    async def redis_keys(request):
        return str_resp(rd.keys())

    @app.get("/flush")
    async def redis_flush(request):
        return str_resp(rd.flushdb())

    @app.get("/exists/<key>")
    async def redis_exists(request, key):
        return str_resp(rd.exists(key))

    @app.get("/expire/<key>/<seconds>")
    async def redis_expire(request, key, seconds):
        return str_resp(rd.expire(key, seconds))

    @app.get("/ttl/<key>")
    async def redis_ttl(request, key):
        return str_resp(rd.ttl(key))

    @app.get("/type/<key>")
    async def redis_type(request, key):
        return str_resp(rd.type(key))

    @app.get("/randomkey")
    async def redis_randomkey(request):
        return str_resp(rd.randomkey())

    @app.get("/rename/<key>/<newkey>")
    async def redis_rename(request, key, newkey):
        return str_resp(rd.rename(key, newkey))

    @app.get("/renamenx/<key>/<newkey>")
    async def redis_renamenx(request, key, newkey):
        return str_resp(rd.renamenx(key, newkey))

    @app.get("/move/<key>/<db>")
    async def redis_move(request, key, db):
        return str_resp(rd.move(key, db))

    @app.get("/dbsize")
    async def redis_dbsize(request):
        return str_resp(rd.dbsize())

    @app.get("/ping")
    async def redis_ping(request):
        return str_resp(rd.ping())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=3000, dev=True)
