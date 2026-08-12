from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector
from mysql.connector import Error
import joblib, re, os, secrets
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-key')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
model = joblib.load(os.path.join(BASE_DIR, 'model', 'bullying_model.pkl'))
vectorizer = joblib.load(os.path.join(BASE_DIR, 'model', 'vectorizer.pkl'))

LABEL_INFO = {
    'cyberbullying': {'name':'Cyberbullying','severity':'High','icon':'bi-phone-vibrate','description':'Repeated digital attacks intended to shame, isolate, or intimidate a person.'},
    'hate_speech': {'name':'Hate Speech','severity':'Critical','icon':'bi-exclamation-octagon','description':'Abusive content targeting identity, religion, ethnicity, gender, or another protected group.'},
    'toxic_language': {'name':'Toxic Language','severity':'Medium','icon':'bi-cloud-lightning','description':'Hostile or degrading language that can damage a healthy online conversation.'},
    'harassment': {'name':'Harassment','severity':'High','icon':'bi-person-x','description':'Persistent unwanted statements or pressure directed at another person.'},
    'offensive_words': {'name':'Offensive Words','severity':'Medium','icon':'bi-chat-square-dots','description':'Insults, obscenity, or rude expressions that violate respectful communication.'},
    'threats': {'name':'Threats','severity':'Critical','icon':'bi-shield-exclamation','description':'Language that communicates an intention to harm, attack, or punish someone.'},
    'normal': {'name':'Normal Message','severity':'Safe','icon':'bi-shield-check','description':'The message does not show a strong harmful-content pattern.'}
}


def db_connection():
    # Read database configuration from environment variables (useful for hosting on Render)
    import urllib.parse
    
    # If a database URL is provided (e.g. mysql://user:pass@host:port/db)
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        url = urllib.parse.urlparse(db_url)
        return mysql.connector.connect(
            host=url.hostname,
            port=url.port or 3306,
            user=url.username,
            password=url.password,
            database=url.path.lstrip('/')
        )
    
    # Fallback to individual environment variables or localhost defaults
    return mysql.connector.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        user=os.environ.get('DB_USER', 'root'),
        password=os.environ.get('DB_PASSWORD', ''),
        database=os.environ.get('DB_NAME', 'bullying_detection_db'),
        port=int(os.environ.get('DB_PORT', 3306))
    )


def init_database():
    try:
        conn = db_connection(); cur = conn.cursor()
        # Create users table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                fullname VARCHAR(100) NOT NULL,
                username VARCHAR(50) NOT NULL UNIQUE,
                email VARCHAR(100) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user'
            )
        """)
        # Create messages table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                message_text TEXT NOT NULL,
                prediction VARCHAR(50) NOT NULL,
                confidence_score DECIMAL(5,2) NOT NULL
            )
        """)
        
        # Run migrations
        migrations = [
            "ALTER TABLE users ADD COLUMN phone VARCHAR(30) NULL",
            "ALTER TABLE users ADD COLUMN bio TEXT NULL",
            "ALTER TABLE users ADD COLUMN reset_token VARCHAR(120) NULL",
            "ALTER TABLE users ADD COLUMN reset_expires DATETIME NULL",
            "ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE messages ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ]
        for sql in migrations:
            try: cur.execute(sql)
            except Error as e:
                if e.errno != 1060: pass
        
        # Seed default admin user if not exists, or update it to ensure correct credentials
        cur.execute("SELECT id FROM users WHERE username = 'admin'")
        admin_user = cur.fetchone()
        admin_pwd = generate_password_hash('admin123')
        if not admin_user:
            cur.execute("""
                INSERT INTO users (fullname, username, email, password, role)
                VALUES ('System Administrator', 'admin', 'admin@safetext.ai', %s, 'admin')
            """, (admin_pwd,))
        else:
            cur.execute("""
                UPDATE users 
                SET fullname = 'System Administrator', email = 'admin@safetext.ai', password = %s, role = 'admin' 
                WHERE username = 'admin'
            """, (admin_pwd,))
            
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print('Database migration/seed note:', e)

# Initialize database tables on application startup
init_database()



def clean_text(text):
    text = str(text).lower()
    text = re.sub(r'https?://\S+|www\.\S+', ' ', text)
    text = re.sub(r'[^a-zA-Z\s\'’]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def predict_message(text):
    cleaned = clean_text(text)
    vec = vectorizer.transform([cleaned])
    prediction = str(model.predict(vec)[0])
    probabilities = model.predict_proba(vec)[0]
    confidence = float(max(probabilities) * 100)
    return prediction, round(confidence, 2), LABEL_INFO.get(prediction, LABEL_INFO['normal'])


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Administrator access is required.', 'danger')
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped


def verify_password(stored, supplied):
    if stored and stored.startswith(('pbkdf2:', 'scrypt:')):
        return check_password_hash(stored, supplied)
    return stored == supplied


@app.context_processor
def inject_globals():
    return {'label_info': LABEL_INFO, 'current_year': datetime.now().year}


@app.route('/')
def home(): return render_template('index.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('identity','').strip(); password = request.form.get('password','')
        conn=db_connection(); cur=conn.cursor(dictionary=True)
        cur.execute('SELECT * FROM users WHERE username=%s OR email=%s LIMIT 1',(identity,identity)); user=cur.fetchone()
        cur.close(); conn.close()
        if user and verify_password(user.get('password'), password):
            session.update(user_id=user['id'], username=user['username'], fullname=user.get('fullname'), role=user['role'])
            flash('Welcome back, '+(user.get('fullname') or user['username'])+'!', 'success')
            return redirect(url_for('admin') if user['role']=='admin' else url_for('dashboard'))
        flash('Invalid username/email or password.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        fullname=request.form.get('fullname','').strip(); username=request.form.get('username','').strip()
        email=request.form.get('email','').strip().lower(); password=request.form.get('password',''); confirm=request.form.get('confirm_password','')
        if len(password)<6: flash('Password must contain at least 6 characters.','warning')
        elif password!=confirm: flash('The passwords do not match.','warning')
        else:
            conn=db_connection(); cur=conn.cursor()
            try:
                cur.execute('INSERT INTO users (fullname,username,email,password,role) VALUES (%s,%s,%s,%s,%s)',(fullname,username,email,generate_password_hash(password),'user'))
                conn.commit(); flash('Registration successful. You can now log in.','success'); return redirect(url_for('login'))
            except Error as e:
                flash('The username or email address already exists.','danger')
            finally: cur.close(); conn.close()
    return render_template('register.html')

@app.route('/forgot-password', methods=['GET','POST'])
def forgot_password():
    reset_link=None
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); token=secrets.token_urlsafe(32); expires=datetime.now()+timedelta(minutes=30)
        conn=db_connection(); cur=conn.cursor(); cur.execute('UPDATE users SET reset_token=%s, reset_expires=%s WHERE email=%s',(token,expires,email)); affected=cur.rowcount; conn.commit(); cur.close(); conn.close()
        if affected: reset_link=url_for('reset_password',token=token,_external=True)
        flash('If the email exists, a password-reset link has been created.','info')
    return render_template('forgot_password.html', reset_link=reset_link)

@app.route('/reset-password/<token>', methods=['GET','POST'])
def reset_password(token):
    conn=db_connection(); cur=conn.cursor(dictionary=True); cur.execute('SELECT * FROM users WHERE reset_token=%s AND reset_expires>NOW()', (token,)); user=cur.fetchone()
    if not user: cur.close(); conn.close(); flash('This reset link is invalid or has expired.','danger'); return redirect(url_for('forgot_password'))
    if request.method=='POST':
        password=request.form.get('password',''); confirm=request.form.get('confirm_password','')
        if len(password)<6: flash('Password must contain at least 6 characters.','warning')
        elif password!=confirm: flash('The passwords do not match.','warning')
        else:
            cur.execute('UPDATE users SET password=%s, reset_token=NULL, reset_expires=NULL WHERE id=%s',(generate_password_hash(password),user['id'])); conn.commit(); cur.close(); conn.close()
            flash('Password reset successful. Please log in.','success'); return redirect(url_for('login'))
    cur.close(); conn.close(); return render_template('reset_password.html')

@app.route('/dashboard')
@login_required
def dashboard():
    conn=db_connection(); cur=conn.cursor(dictionary=True)
    cur.execute('SELECT COUNT(*) total FROM messages WHERE user_id=%s',(session['user_id'],)); total=cur.fetchone()['total']
    cur.execute("SELECT COUNT(*) harmful FROM messages WHERE user_id=%s AND prediction<>'normal'",(session['user_id'],)); harmful=cur.fetchone()['harmful']
    cur.execute("SELECT COUNT(*) safe FROM messages WHERE user_id=%s AND prediction='normal'",(session['user_id'],)); safe=cur.fetchone()['safe']
    cur.execute('SELECT * FROM messages WHERE user_id=%s ORDER BY id DESC LIMIT 5',(session['user_id'],)); recent=cur.fetchall()
    cur.close(); conn.close(); return render_template('dashboard.html',total=total,harmful=harmful,safe=safe,recent=recent)

@app.route('/detect', methods=['GET','POST'])
@login_required
def detect():
    if request.method=='POST':
        text=request.form.get('message','').strip()
        if not text: flash('Please enter a message to analyse.','warning'); return render_template('detect.html')
        prediction,confidence,details=predict_message(text)
        conn=db_connection(); cur=conn.cursor(); cur.execute('INSERT INTO messages (user_id,message_text,prediction,confidence_score) VALUES (%s,%s,%s,%s)',(session['user_id'],text,prediction,confidence)); record_id=cur.lastrowid; conn.commit(); cur.close(); conn.close()
        session['last_result_id']=record_id
        return redirect(url_for('detection_result',record_id=record_id))
    return render_template('detect.html')

@app.route('/result/<int:record_id>')
@login_required
def detection_result(record_id):
    conn=db_connection(); cur=conn.cursor(dictionary=True)
    if session.get('role')=='admin': cur.execute('SELECT * FROM messages WHERE id=%s',(record_id,))
    else: cur.execute('SELECT * FROM messages WHERE id=%s AND user_id=%s',(record_id,session['user_id']))
    record=cur.fetchone(); cur.close(); conn.close()
    if not record: flash('Detection result not found.','danger'); return redirect(url_for('history'))
    return render_template('result.html',record=record,details=LABEL_INFO.get(record['prediction'],LABEL_INFO['normal']))

@app.route('/history')
@login_required
def history():
    conn=db_connection(); cur=conn.cursor(dictionary=True); cur.execute('SELECT * FROM messages WHERE user_id=%s ORDER BY id DESC',(session['user_id'],)); records=cur.fetchall(); cur.close(); conn.close()
    return render_template('history.html',records=records)

@app.route('/history/delete/<int:record_id>', methods=['POST'])
@login_required
def delete_history(record_id):
    conn=db_connection(); cur=conn.cursor(); cur.execute('DELETE FROM messages WHERE id=%s AND user_id=%s',(record_id,session['user_id'])); conn.commit(); cur.close(); conn.close(); flash('Prediction record deleted.','success'); return redirect(url_for('history'))

@app.route('/profile', methods=['GET','POST'])
@login_required
def profile():
    conn=db_connection(); cur=conn.cursor(dictionary=True)
    if request.method=='POST':
        cur.execute('UPDATE users SET fullname=%s,email=%s,phone=%s,bio=%s WHERE id=%s',(request.form.get('fullname'),request.form.get('email'),request.form.get('phone'),request.form.get('bio'),session['user_id'])); conn.commit(); session['fullname']=request.form.get('fullname'); flash('Profile updated successfully.','success')
    cur.execute('SELECT * FROM users WHERE id=%s',(session['user_id'],)); user=cur.fetchone(); cur.close(); conn.close(); return render_template('profile.html',user=user)

@app.route('/contact', methods=['GET','POST'])
def contact():
    if request.method=='POST': flash('Thank you. Your message has been received.','success'); return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/about')
def about(): return render_template('about.html')

@app.route('/admin')
@admin_required
def admin():
    conn=db_connection(); cur=conn.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) total_users FROM users WHERE role<>'admin'"); total_users=cur.fetchone()['total_users']
    cur.execute('SELECT COUNT(*) total FROM messages'); total=cur.fetchone()['total']
    cur.execute("SELECT COUNT(*) harmful FROM messages WHERE prediction<>'normal'"); harmful=cur.fetchone()['harmful']
    cur.execute("SELECT COUNT(*) safe FROM messages WHERE prediction='normal'"); safe=cur.fetchone()['safe']
    cur.execute("SELECT COUNT(DISTINCT user_id) total_bullies FROM messages WHERE prediction<>'normal'"); total_bullies=cur.fetchone()['total_bullies']
    cur.execute('SELECT prediction, COUNT(*) value FROM messages GROUP BY prediction'); category_rows=cur.fetchall()
    category_stats={row['prediction']:row['value'] for row in category_rows}
    cur.execute("SELECT DATE(created_at) day, COUNT(*) value FROM messages WHERE created_at>=DATE_SUB(CURDATE(),INTERVAL 6 DAY) GROUP BY DATE(created_at) ORDER BY day")
    daily=cur.fetchall(); daily_map={str(r['day']):r['value'] for r in daily}; labels=[]; values=[]
    for i in range(6,-1,-1):
        d=(datetime.now()-timedelta(days=i)).date(); labels.append(d.strftime('%a')); values.append(daily_map.get(str(d),0))
    cur.execute('SELECT m.*,u.username FROM messages m LEFT JOIN users u ON m.user_id=u.id ORDER BY m.id DESC LIMIT 8'); recent_predictions=cur.fetchall()
    cur.execute("SELECT fullname,username,created_at FROM users ORDER BY id DESC LIMIT 5"); recent_users=cur.fetchall()
    cur.close(); conn.close()
    return render_template('admin.html',total_users=total_users,total=total,harmful=harmful,safe=safe,total_bullies=total_bullies,category_stats=category_stats,daily_labels=labels,daily_values=values,recent_predictions=recent_predictions,recent_users=recent_users)

@app.route('/users')
@admin_required
def users():
    conn=db_connection(); cur=conn.cursor(dictionary=True); cur.execute("SELECT id,fullname,username,email,role,created_at FROM users ORDER BY id DESC"); rows=cur.fetchall(); cur.close(); conn.close(); return render_template('users.html',users=rows)

@app.route('/admin/predictions')
@admin_required
def admin_predictions():
    conn=db_connection(); cur=conn.cursor(dictionary=True); cur.execute('SELECT m.*,u.username FROM messages m LEFT JOIN users u ON m.user_id=u.id ORDER BY m.id DESC'); records=cur.fetchall(); cur.close(); conn.close(); return render_template('admin_predictions.html',records=records)

@app.route('/delete/<int:record_id>', methods=['POST'])
@admin_required
def delete_record(record_id):
    conn=db_connection(); cur=conn.cursor(); cur.execute('DELETE FROM messages WHERE id=%s',(record_id,)); conn.commit(); cur.close(); conn.close(); flash('Prediction deleted.','success'); return redirect(request.referrer or url_for('admin_predictions'))

@app.route('/logout')
def logout(): session.clear(); flash('You have been logged out.','info'); return redirect(url_for('login'))

if __name__=='__main__':
    app.run(debug=True)
