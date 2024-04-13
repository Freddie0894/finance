import os
import sqlite3

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET"])
@login_required
def index():

    # Retrieve the current user's id.
    currentUser = request.form.get("user_id")

    # get all the stocks users owns from the database
    allStocks = db.execute("SELECT symbol FROM transactions WHERE user_id = :user_id", user_id=session["user_id"])
    stocks = db.execute("SELECT * FROM transactions WHERE user_id = :user_id", user_id=session["user_id"])

    if not stocks:
        userCash  = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
        userBalance = round(userCash[0]["cash"], 2)
        return render_template("index.html", balance=userBalance)

    else:
        totalStocks = 0

        # Initialize lists to store symbols and current prices
        symbols = []
        currentPrices = []

        # For each stock, get the current price
        for stock in stocks:
            symbol = stock["symbol"]

            # get current price
            currentStock = lookup(symbol)

            if currentStock is not None:
                currentPrice = usd(currentStock["price"])
                symbols.append(symbol)
                currentPrices.append(currentPrice)



                # get the total assets price
                allPrices = db.execute("SELECT SUM(price) AS price FROM transactions WHERE user_id = :user_id", user_id=session["user_id"])
                sharePrice = round(allPrices[0]['price'], 2)
                price = usd(float(sharePrice))

                onePrice  = db.execute("SELECT price FROM transactions WHERE user_id = :user_id", user_id=session["user_id"])
                for i in range(len(onePrice)):
                    onePrice [i]['price'] = usd(float(onePrice[i]['price']))


                # query user for cash balance
                userCash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
                userBalance = round(userCash[0]["cash"], 2)
                portfolio = usd(float(userBalance))


        # Render the index page, passing (stocks, total cash, total assets)
        return render_template('index.html', onePrice=onePrice, stocks=stocks, allStocks=allStocks, price=price, portfolio=portfolio, currentPrices=currentPrices)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    user_id = session["user_id"]
    stocks = db.execute("SELECT * FROM transactions WHERE user_id = :user_id", user_id=session["user_id"])


    if request.method == "GET":

        balance = usd(db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]['cash'])
        return render_template("buy.html", balance=balance)

    elif request.method == "POST":

        # Retrieve the form data:
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if not shares.isdigit() or int(shares) <= 0:
            return apology("Invalid number of shares.", 400)

        elif lookup(symbol) is None:
            return apology("The stock doesn't exist. Please check for typing errors in your search.", 400)

        else:

            shares = round(float(shares), 2)
            formatted_shares = "{:.2f}".format(shares)

            # get current price
            getSymbol = lookup(symbol)

            # calculate cost of transaction
            buyPrice = round(getSymbol['price'] * shares, 2)

            usdPrice = usd(float(buyPrice))
            # check user money
            userMoney = db.execute("SELECT cash FROM users WHERE id = ?", user_id)

            if userMoney[0]['cash'] < buyPrice:
                return apology("Insufficent Balance. Please make a deposit to continue.", 400)
            else:

                # update cash in database
                db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", buyPrice, user_id)

                # Check if stock already exists
                userStocks = db.execute("SELECT symbol, shares, price, time FROM transactions WHERE user_id = ? AND symbol = ? AND transaction_type = 'buy'", user_id, symbol)

                if not userStocks:
                    # Insert new row if stock doesn't exist
                    db.execute("INSERT INTO transactions (user_id, symbol, shares, price, transaction_type) VALUES (?, ?, ?, ?, ?)", user_id, symbol, shares, buyPrice, 'buy')
                else:
                    # Update existing row if stock exists
                    updated_shares = userStocks[0]['shares'] + shares
                    db.execute("UPDATE transactions SET shares = ? WHERE user_id = ? AND symbol = ?", updated_shares, user_id, symbol)

                    #update tot shares price adding the last bought to the price of the bought share
                    db.execute("UPDATE transactions SET price = price + ? WHERE user_id = ? AND symbol = ?", buyPrice, user_id, symbol)

                # show current number of shares
                stocks = db.execute("SELECT shares FROM transactions WHERE user_id = ? AND symbol = ?", user_id, symbol)
                shares_value = stocks[0]['shares']

                # find time of transaction
                time = datetime.now()

                # insert row in history table
                history = db.execute("INSERT INTO history (user_id, symbol, shares, price, time, transaction_type) VALUES (?, ?, ?, ?, ?, ?)", user_id, symbol, shares, buyPrice, time, 'buy')

            remaining_credit = usd(userMoney[0]['cash'] - buyPrice)
            return render_template("bought.html", symbol=getSymbol, formatted_shares=formatted_shares, shares_value=shares_value, usdPrice=usdPrice, remaining_credit=remaining_credit)




@app.route("/history", methods=["GET"])
@login_required
def history():

     user_id = session["user_id"]
     history = db.execute("SELECT * FROM history WHERE user_id = :user_id", user_id=session["user_id"])
     return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Must provide username.", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Must provide password.", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
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

    symbol = request.form.get("symbol")

    if request.method == "GET":
        return render_template("quote.html")

    elif request.method == "POST":
        if lookup(symbol) is None:
            return apology("Symbol required.")

        else:
            getSymbol = lookup(symbol)
            usdSymbol = usd(getSymbol['price'])

            return render_template("quoted.html", usdSymbol=usdSymbol, symbol=getSymbol)



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        existing_user = db.execute("SELECT * FROM users WHERE username = ?", username)

        if len(existing_user) > 0:
            return apology("Username already exist.", 400)

        elif username is None or username == "":
            return apology("Username required.", 400)

        elif password is None or password == "":
            return apology("Password required.", 400)

        elif password != confirmation:
            return apology("Passwords must match.", 400)

        hashed_password = generate_password_hash(password)

        rows = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hashed_password)
        return redirect("/login")


    else:
        return render_template("register.html")




# IL PROBLEMA E' QUI
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():


    user_id = session["user_id"]
    shares = db.execute("SELECT symbol FROM transactions WHERE user_id = ?", user_id)


    if request.method == "GET":
        return render_template("sell.html", shares=shares)

    elif request.method == "POST":

        # calculate total shares in database
        symbol = request.form.get("symbol")

        boughtQuery = db.execute("SELECT SUM(shares) FROM transactions WHERE user_id = ? AND symbol = ? AND transaction_type = 'buy'", user_id, symbol)
        bought = boughtQuery[0]["SUM(shares)"] if boughtQuery and boughtQuery[0]["SUM(shares)"] else 0

        currentShares = bought
        print(currentShares)

        shareNumber = int(request.form.get("shares"))

        #if user hasn't enough shares
        if shareNumber > currentShares:
            return apology("Sorry, you have not enough shares to sell.")

        else:
            # calculate total to sell
            stockInfo = lookup(symbol)
            currentPrice = stockInfo["price"]
            totalToSell = shareNumber * currentPrice
            usdToSell = usd(shareNumber * currentPrice)

            # update number of shares in database
            newTotal = db.execute("UPDATE transactions SET shares = shares - ? WHERE user_id = ? AND symbol = ? AND transaction_type = 'buy'", shareNumber, user_id, symbol)

            # update user's cash
            newBalance = usd(db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", totalToSell, user_id))

            # update tot shares price subtracting the last bought to the price of the bought share
            db.execute("UPDATE transactions SET price = price - ? WHERE user_id = ? AND symbol = ?", totalToSell, user_id, symbol)

            # get the updated user balance
            userMoney = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
            remaining_credit = usd(userMoney[0]['cash'])


            # Get the updated quantity of shares
            newQty = db.execute("SELECT shares FROM transactions WHERE user_id = ? AND symbol = ?", user_id, symbol)
            quantity = newQty[0]["shares"]

            # if users sells all shares of a stock
            if quantity <= 0:
                # delete stock in database
                deleteStock = db.execute("DELETE FROM transactions WHERE user_id = ? AND symbol = ? AND transaction_type = 'buy'", user_id, symbol)


            # find time of transaction
            time = datetime.now()
            # insert row in history table
            history = db.execute("INSERT INTO history (user_id, symbol, shares, price, time, transaction_type) VALUES (?, ?, ?, ?, ?, ?)", user_id, symbol, shareNumber, currentPrice, time, 'sell')

        return render_template("sold.html", shares_sold=shareNumber, total_price=usdToSell, symbol=symbol, remaining_credit=remaining_credit)

