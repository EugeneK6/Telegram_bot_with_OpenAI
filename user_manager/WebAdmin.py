from flask import Flask, render_template, request, redirect, url_for, flash
import psycopg2
import os
import logging
from logfmter import Logfmter

# Configure logging
formatter = Logfmter(
    keys=["at", "process", "level", "msg"],
    mapping={"at": "asctime", "process": "processName", "level": "levelname", "msg": "message"},
    datefmt='%H:%M:%S %d/%m/%Y'
)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
file_handler = logging.FileHandler("./logs/user-manager.log")
file_handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[stream_handler, file_handler]
)

app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY")


def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"))
    return conn


@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username FROM allowed_users ORDER BY user_id")
    allowed_users = cur.fetchall()

    cur.execute("SELECT * FROM identified_user")
    identified_users = cur.fetchall()

    cur.execute("SELECT user_id, balance FROM user_credit ORDER BY user_id")
    user_balances = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('index.html', allowed_users=allowed_users, identified_users=identified_users,
                           user_balances=user_balances)




@app.route('/allow', methods=['POST'])
def allow_user():
    user_id = request.form.get('user_id')
    app.logger.info(f'Allowing user with ID: {user_id}')
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
        app.logger.error(f'Error allowing user: {str(e)}')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))


@app.route('/disable', methods=['POST'])
def disable_user():
    user_id = request.form.get('user_id')
    app.logger.info(f'Disabling user with ID: {user_id}')
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
        app.logger.error(f'Error disabling user: {str(e)}')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))


@app.route('/set_balance', methods=['POST'])
def set_balance():
    user_id = request.form.get('user_id')
    new_balance = request.form.get('new_balance')
    app.logger.info(f'Setting balance for user ID {user_id} to {new_balance}')
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE user_credit SET balance = %s WHERE user_id = %s", (new_balance, user_id))
        conn.commit()
        flash(f"Balance updated for user ID {user_id}.", 'success')
    except Exception as e:
        flash(f"Error updating balance: {str(e)}", 'danger')
        app.logger.error(f'Error updating balance for user ID {user_id}: {str(e)}')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))

# function reset user's credit to 0.00
@app.route('/reset_balance/<int:user_id>', methods=['POST'])
def reset_balance(user_id):
    app.logger.info(f'Resetting balance for user ID {user_id}')
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE user_credit SET balance = 0 WHERE user_id = %s", (user_id,))
        conn.commit()
        flash(f"Balance reset for user ID {user_id}.", 'success')
    except Exception as e:
        flash(f"Error resetting balance: {str(e)}", 'danger')
        app.logger.error(f'Error resetting balance for user ID {user_id}: {str(e)}')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
