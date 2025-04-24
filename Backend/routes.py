from sqlalchemy import inspect
from flask import session,render_template, request, flash, redirect, url_for,make_response,request
import requests
from app import app, db
from models import Credential,IndividualDetails
import os
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from sqlalchemy.orm import aliased
from datetime import datetime
from sqlalchemy import func
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
from flask import render_template, send_file
from sqlalchemy.sql import case,text

@app.route("/")
def base_home():
    return render_template("home.html")

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user_cred = Credential.query.filter_by(username=username).first()

        if not user_cred:
            flash("Invalid username!", "error")
            return redirect(url_for('login_page'))

        if user_cred.password!=password:
            flash("Incorrect password!", "error")
            return redirect(url_for('login_page'))

        # Login successful, store session info
        session['username'] = user_cred.username
        session['flag'] = user_cred.flag  # assuming flag = 'individual', 'organization', etc.

        # Redirect based on flag
        if user_cred.flag == 'individual':
            return redirect(url_for('individual_home'))
        else:
            flash("User type not handled yet.", "warning")
            return redirect(url_for('login_page'))

    return render_template("login.html")
    

@app.route('/register-individual', methods=['GET', 'POST'])
def register_individual():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        username = request.form.get('username')
        print(username)
        password = request.form.get('password')

        # Check if username already exists
        if Credential.query.filter_by(username=username).first():
            flash("Username already exists!", "error")
            return redirect(url_for('register_individual'))

        # Create and commit the new user
        new_user = IndividualDetails(username, first_name, last_name, email)
        new_cred = Credential(username, password, flag='individual')  # status defaults to 'active'

        try:
            db.session.add(new_user)
            db.session.add(new_cred)
            db.session.commit()
            flash("Registration successful!", "success")
            return redirect(url_for('login_page'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error during registration: {str(e)}", "error")
            return redirect(url_for('register_individual'))

    return render_template('registration_individual.html')

@app.route('/individual_home', methods=["GET", "POST"])
def individual_home():
    if 'username' not in session:
        flash("You need to log in first.", "error")
        return redirect(url_for('login_page'))
    username=session['username']
    user = IndividualDetails.query.filter_by(username=username).first()
    first_name=user.first_name
    return render_template('individual/home.html',first_name=first_name)


@app.route("/ide", methods=["GET", "POST"])
def index():
    output = ""
    code = ''''''  # default code

    if request.method == "POST":
        code = request.form["code"]

        response = requests.post("https://emkc.org/api/v2/piston/execute", json={
            "language": "python3",
            "version": "3.10.0",
            "files": [{"name": "main.py", "content": code}]
        })

        result = response.json()
        output = result.get("run", {}).get("stdout", "")
        error = result.get("run", {}).get("stderr", "")
        if error:
            output += "\nError:\n" + error

    return render_template("ide.html", output=output, code=code)


@app.route('/individual/friends')
def friends():
    return render_template('individual/friends.html')

@app.route('/individual/add_quiz')
def add_quiz():
    return render_template('individual/add_quiz.html')

@app.route('/individual/attempted_quizes')
def attempted_quizes():
    return render_template('individual/attempted_quizes.html')

@app.route('/logout')
def logout():
    session.clear()  # Clear session data
    flash("You have been logged out.", "success")

    # Prevent caching on the login and restricted pages
    response = make_response(redirect(url_for('login_page')))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response