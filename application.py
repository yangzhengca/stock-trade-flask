import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Query user's holded stock in holds table
    rows = db.execute("SELECT * FROM holds WHERE user_id = :userId ORDER BY symbol", userId=session["user_id"])
    
    stock_list = []
    
    for row in rows:
        stock = {}
        quoted = lookup(row["symbol"])
        stock["symbol"] = row["symbol"]
        stock["name"] = quoted["name"]
        stock["shares"] = row["total_shares"]
        stock["price"] = quoted["price"]
        stock["total"] = quoted["price"] * row["total_shares"]
        stock_list.append(stock)
        
    # Query cash from users table
    row = db.execute("SELECT cash FROM users WHERE id = :userId", userId=session["user_id"])
    cash = row[0]["cash"]
    
    # Cal total 
    total = cash
    
    for stock in stock_list:
        total = total + stock["total"]
    
    return render_template("index.html", stock_list=stock_list, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)
        
        # Ensure shares was submitted   
        elif not request.form.get("shares"):
            return apology("must provide a number of shares", 400)
            
        # Ensure shares number is valid  
        elif not (request.form.get("shares")).isdigit():
            return apology("invalid number of shares", 400)
        
        elif int(request.form.get("shares")) <= 0:
            return apology("invalid number of shares", 400)
        
        # Lookup with input symbol
        quoted = lookup(request.form.get("symbol"))
            
        # Ensure symbol is valid 
        if not quoted:
            return apology("invalid symbol", 400)
        
        # Cal purchase price 
        purchase_price = quoted["price"]*int(request.form.get("shares"))
        
        # Query user's cash in datebase
        row = db.execute("SELECT cash FROM users WHERE id = :sessionId", sessionId=session["user_id"])
        
        cashOwned = row[0]["cash"]
        
        # Check if user has enough cash for purchase
        if cashOwned < purchase_price:
            return apology("not enough cash for the purchase", 400)
        
        # Add trade recored to trades table
        db.execute("INSERT INTO trades (user_id, symbol, stock_name, price, shares) VALUES(?, ?, ?, ?, ?)",
                   session["user_id"], quoted["symbol"], quoted["name"], quoted["price"], int(request.form.get("shares")))
        
        rowHolds = db.execute("SELECT * FROM holds WHERE user_id = :sessionId and symbol = :symbolPurchased", 
                              sessionId=session["user_id"], symbolPurchased=quoted["symbol"])
        
        if len(rowHolds) == 1:
            db.execute("UPDATE holds SET total_shares = :newTotalShares WHERE user_id = :sessionId and symbol = :symbolPurchased",
                       newTotalShares=rowHolds[0]["total_shares"]+int(request.form.get("shares")), sessionId=session["user_id"], symbolPurchased=quoted["symbol"])
        else:
            db.execute("INSERT INTO holds (user_id, symbol, total_shares) VALUES(?, ?, ?)", 
                       session["user_id"], quoted["symbol"], int(request.form.get("shares")))
        
        # Update user's cash in users table
        db.execute("UPDATE users SET cash = :newCash WHERE id = :sessionId", 
                   newCash=cashOwned-purchase_price, sessionId=session["user_id"])
        
        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Query trade records from trades table
    trades = db.execute("SELECT * FROM trades WHERE user_id = :sessionId", sessionId=session["user_id"])
    return render_template("history.html", trades=trades)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)
            
        # Call lookup to get quoted data
        quoted = lookup(request.form.get("symbol"))
        
        # Ensure quoted is not null
        if not quoted:
            return apology("no data founded with your input symbol", 400)
        print(quoted)
        # Redirect user to quoted page with quoted data
        return render_template("quoted.html", quoted=quoted)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)
            
        # Ensure confirmation password was submitted
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)
            
        # Ensure password was match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        
        # Check if username already exists
        if len(rows) == 1: 
            return apology("username already exists", 400)

        hashed = generate_password_hash(request.form.get("password"))
        username = request.form.get("username")
        # Insert user to users table
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hashed)

        # Redirect user to login page
        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")
    
    return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)
        
        # Ensure shares was submitted   
        elif not request.form.get("shares"):
            return apology("must provide a number of shares", 400)
        # Ensure shares number is valid      
        elif int(request.form.get("shares")) <= 0:
            return apology("invalid number of shares", 400)
        
        # Lookup with input symbol
        quoted = lookup(request.form.get("symbol"))
            
        # Ensure symbol is valid 
        if not quoted:
            return apology("invalid symbol", 400)
        
        # Query user's stock shares
        holdShares = db.execute("SELECT total_shares FROM holds WHERE user_id = :sessionId and symbol = :requestSymbol", 
                                sessionId=session["user_id"], requestSymbol=request.form.get("symbol"))
        
        if len(holdShares) != 1:
            return apology("you don't have any shares of that stock", 400)
        
        # Query cash from users table
        row = db.execute("SELECT cash FROM users WHERE id = :userId", userId=session["user_id"])
        cashOwned = row[0]["cash"]
        
        sell_price = quoted["price"]*int(request.form.get("shares"))
        
        if holdShares[0]["total_shares"] < int(request.form.get("shares")):
            return apology("you don't have that many shares of the stock", 400)
        elif holdShares[0]["total_shares"] == int(request.form.get("shares")):
            # Update holds table
            db.execute("DELETE FROM holds WHERE symbol = :requestSymbol", requestSymbol=request.form.get("symbol"))
            # Update trades table
            db.execute("INSERT INTO trades (user_id, symbol, stock_name, price, shares) VALUES(?, ?, ?, ?, ?)", 
                       session["user_id"], quoted["symbol"], quoted["name"], quoted["price"], -int(request.form.get("shares")))
            # Update users table
            db.execute("UPDATE users SET cash = :newCash WHERE id = :sessionId", 
                       newCash=cashOwned+sell_price, sessionId=session["user_id"])
        else:
            # Update holds table
            db.execute("UPDATE holds SET total_shares = :newShares WHERE user_id = :sessionId and symbol = :requestSymbol", 
                       newShares=holdShares[0]["total_shares"]-int(request.form.get("shares")), sessionId=session["user_id"], requestSymbol=request.form.get("symbol"))
            # Update trades table
            db.execute("INSERT INTO trades (user_id, symbol, stock_name, price, shares) VALUES(?, ?, ?, ?, ?)", 
                       session["user_id"], quoted["symbol"], quoted["name"], quoted["price"], -int(request.form.get("shares")))
            # Update users table
            db.execute("UPDATE users SET cash = :newCash WHERE id = :sessionId", 
                       newCash=cashOwned+sell_price, sessionId=session["user_id"])
        
        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        # Query user's stock symbol data
        stocks = db.execute("SELECT symbol FROM holds WHERE user_id = :sessionId ORDER BY symbol", sessionId=session["user_id"])
        return render_template("sell.html", stocks=stocks)


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Deposit cash."""
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("deposit"):
            return apology("must provide a number of deposit", 403)
        # Ensure deposit number is valid      
        elif int(request.form.get("deposit")) <= 0:
            return apology("invalid number of deposit", 403)
        
        # Query cash from users table
        row = db.execute("SELECT cash FROM users WHERE id = :userId", userId=session["user_id"])
        cashOwned = row[0]["cash"]
            
        # Update user's cash in users table
        db.execute("UPDATE users SET cash = :newCash WHERE id = :sessionId", newCash=cashOwned +
                   int(request.form.get("deposit")), sessionId=session["user_id"])

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("deposit.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
