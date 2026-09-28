# app.py 
import sqlite3
from functools import wraps
from flask import Flask, g, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash


DATABASE = 'database.db'

# initialise app
app = Flask(__name__) 
app.secret_key = 'change-this-to-something-random-before-deploying'


# --- Database helpers ---

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv        

def write_db(query, args=()):
    db = get_db()
    db.execute(query, args)
    db.commit()


# --- Auth helper ---

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# --- Public routes ---

@app.route('/')
def home():
    return render_template ('home.html')

@app.route('/brand')
def brand():
    # Get all brands to populate the dropdown
    brands = query_db('SELECT BrandID, name FROM Brands ORDER BY name')
    years = query_db('SELECT Release FROM Release ORDER BY Release')

    # Read filter values from the URL query string
    BrandID = request.args.get('BrandID', '')
    Release = request.args.get('Release', '')
    search   = request.args.get('search', '')

    # Build the WHERE clause dynamically based on what filters are active
    conditions = []
    args = []

    if BrandID:
        conditions.append('Boots.BrandID = ?')
        args.append(BrandID)

    if Release:
        conditions.append('Boots.Release = ?')
        args.append(Release)

    if search:
        conditions.append('Boots.Name LIKE ?')
        args.append(f'%{search}%')

    where_clause = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''

    sql = f"""
        SELECT Boots.BootID, Brands.Name, Boots.Name, Boots.ImageURL1
        FROM Boots
        JOIN Brands ON Boots.BrandID = Brands.BrandID
        JOIN Release ON Boots.Release = Release.Release
        {where_clause}
    """
    results = query_db(sql, tuple(args))

    return render_template('brand.html',
                           results=results,
                           brands=brands,
                           selected_brand=BrandID,
                           years=years,
                           selected_year=Release,
                           search=search)

@app.route('/boot/<int:id>')
def boot(id):
    # just one boot based on ID
    sql = """SELECT * FROM Boots 
             JOIN Brands ON Brands.BrandID=Boots.BrandID
             WHERE Boots.BootID = ?;"""
    result = query_db(sql,(id,),True)
    return render_template("boot.html", boot=result)

@app.errorhandler(404)
def page_not_found(error):
    # Returns your custom template and the explicit 404 status code
    return render_template('404.html'), 404


# --- Auth routes ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    # If already logged in, go straight to admin
    if 'user_id' in session:
        return redirect(url_for('admin'))

    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = query_db(
            'SELECT user_id, password_hash FROM users WHERE username = ?',
            (username,), one=True
        )

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            return redirect(url_for('admin'))
        else:
            error = 'Invalid username or password.'

    return render_template('admin_login.html', error=error)


@app.route('/admin/logout')
def admin_logout():
    session.pop('user_id', None)
    return redirect(url_for('admin_login'))


# --- Admin routes (protected) ---

@app.route('/admin')
@login_required
def admin():
    sql = """
        SELECT Boots.BootID, Brands.Name, Boots.Name,
               Boots.Release, Boots.Style, Boots.ImageURL1
        FROM Boots
        JOIN Brands ON Boots.BrandID = Brands.BrandID
        ORDER BY Boots.BootID
    """
    boots = query_db(sql)
    return render_template('admin.html', boots=boots)

@app.route('/admin/add', methods=['GET', 'POST'])
@login_required
def admin_add():
    brands = query_db('SELECT BrandID, Name FROM Brands ORDER BY Name')

    if request.method == 'POST':
        write_db(
            'INSERT INTO Boots (BrandID, Name, Brand, Release, Style, Description, ImageURL1, ImageURL2, ImageURL3, ImageURL4, ImageURL5) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (request.form['BrandID'], request.form['Name'],
             request.form['Brand'], request.form['Release'],
             request.form['Style'], request.form['Description'], 
             request.form['ImageURL1'], request.form['ImageURL2'], 
             request.form['ImageURL3'], request.form['ImageURL4'], 
             request.form['ImageURL5'])
        )
        return redirect(url_for('admin'))

    return render_template('admin_form.html',
                           title='Add New Boot',
                           boot=None,
                           brands=brands)

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_edit(id):
    brands = query_db('SELECT BrandID, Name FROM brands ORDER BY Name')

    if request.method == 'POST':
        write_db(
            '''UPDATE Boots
               SET BrandID=?, Name=?, Brand=?, Release=?, Style=?, Description=?,ImageURL1=?, ImageURL2=?, ImageURL3=?, ImageURL4=?, ImageURL5=?
               WHERE BootID=?''',
            (request.form['BrandID'], request.form['Name'],
             request.form['Brand'], request.form['Release'], 
             request.form['Style'], request.form['Description'], 
             request.form['ImageURL1'], request.form['ImageURL2'], 
             request.form['ImageURL3'], request.form['ImageURL4'], 
             request.form['ImageURL5'], id)
        )
        return redirect(url_for('admin'))

    boot = query_db(
         '''SELECT BrandID, Name, Brand, Release, Style, Description,
                ImageURL1, ImageURL2, ImageURL3, ImageURL4, ImageURL5
           FROM Boots
            WHERE BootID = ?''',
        (id,), one=True
    )
    return render_template('admin_form.html',
                           title='Edit Boot',
                           boot=boot,
                           brands=brands)

@app.route('/admin/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete(id):
    write_db('DELETE FROM Boots WHERE BootID = ?', (id,))
    return redirect(url_for('admin'))

if __name__ == "__main__":
    app.run(debug=True)