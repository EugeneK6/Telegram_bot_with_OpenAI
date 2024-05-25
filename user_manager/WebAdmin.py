"""This module manages users access and their balances via web app."""

import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash
import psycopg2
from logfmter import Logfmter

log_to_file = os.getenv('LOG_TO_FILE', 'False') == 'True'

# Configure logging
formatter = Logfmter(
    keys=["at", "process", "level", "msg"],
    mapping={"at": "asctime", "process": "processName", "level": "levelname", "msg": "message"},
    datefmt='%H:%M:%S %d/%m/%Y'
)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

enabled_handlers = [stream_handler]

if log_to_file:
    file_handler = logging.FileHandler("./logs/bot.log")
    file_handler.setFormatter(formatter)
    enabled_handlers.append(file_handler)

logging.basicConfig(
    level=logging.INFO,
    handlers=enabled_handlers
)

# Set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY")


def get_db_connection(
        host=os.getenv("DB_HOST"),
        database=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
):
    """connect to the postgres database."""
    conn = psycopg2.connect(
        host=host,
        database=database,
        user=user,
        password=password
    )
    return conn


@app.route('/')
def index():
    """Renders the index page with allowed users and their balances."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT user_id, username FROM allowed_users ORDER BY user_id")
        allowed_users = cur.fetchall()

        cur.execute("SELECT * FROM identified_user")
        identified_users = cur.fetchall()

        cur.execute("SELECT user_id, balance FROM user_credit ORDER BY user_id")
        user_balances = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    return render_template('index.html', allowed_users=allowed_users, identified_users=identified_users,
                           user_balances=user_balances)

@app.route('/health')
def health():
    """Health check endpoint."""
    conn = get_db_connection()
    cur = conn.cursor()

    healthcheck_log = logging.getLogger('werkzeug')
    healthcheck_log.setLevel(logging.ERROR)

    try:
        cur.execute("SELECT 1")
        cur.fetchone()
        return "OK", 200
    except psycopg2.Error as e:
        return f"Error: {str(e)}", 500
    finally:
        cur.close()
        conn.close()


@app.route('/allow', methods=['POST'])
def allow_user():
    """Allows a user to access the system."""
    user_id = request.form.get('user_id')
    app.logger.info('Allowing user with ID: %s', user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT user_id FROM allowed_users WHERE user_id = %s", (user_id,))
        existing_user = cur.fetchone()
        if existing_user:
            flash(f"User {user_id} is already allowed.", 'info')
        else:
            cur.execute("INSERT INTO allowed_users (user_id, username) "
                        "SELECT user_id, COALESCE(username, first_name, last_name) "
                        "FROM identified_user WHERE user_id = %s", (user_id,))
            conn.commit()
            flash(f"User {user_id} has been allowed.", 'success')
    except Exception as e:
        flash(f"Error allowing user: {str(e)}", 'danger')
        app.logger.error('Error allowing user: %s', e)
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))


@app.route('/disable', methods=['POST'])
def disable_user():
    """Revokes a user's access to the system."""
    user_id = request.form.get('user_id')
    app.logger.info('Disabling user with ID: %s', user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT user_id FROM allowed_users WHERE user_id = %s", (user_id,))
        existing_user = cur.fetchone()
        if not existing_user:
            flash(f"User {user_id} is not currently allowed.", 'info')
        else:
            cur.execute("DELETE FROM allowed_users WHERE user_id = %s", (user_id,))
            conn.commit()
            flash(f"User {user_id} access revoked.", 'warning')
    except Exception as e:
        flash(f"Error disabling user: {str(e)}", 'danger')
        app.logger.error('Error disabling user: %s', e)
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))


@app.route('/set_balance', methods=['POST'])
def set_balance():
    """Sets a user's balance to the specified amount."""
    user_id = request.form.get('user_id')
    new_balance = request.form.get('new_balance')
    app.logger.info('Setting balance for user ID %s to %s', user_id, new_balance)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE user_credit SET balance = %s WHERE user_id = %s", (new_balance, user_id))
        conn.commit()
        flash(f"Balance updated for user ID {user_id}.", 'success')
    except Exception as e:
        flash(f"Error updating balance: {str(e)}", 'danger')
        app.logger.error('Error updating balance for user ID %s: %s', user_id, e)
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))


@app.route('/reset_balance/<int:user_id>', methods=['POST'])
def reset_balance(user_id):
    """Resets a user's balance to zero."""
    app.logger.info('Resetting balance for user ID %s', user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE user_credit SET balance = 0 WHERE user_id = %s", (user_id,))
        conn.commit()
        flash(f"Balance reset for user ID {user_id}.", 'success')
    except Exception as e:
        flash(f"Error resetting balance: {str(e)}", 'danger')
        app.logger.error('Error resetting balance for user ID %s: %s', user_id, e)
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
