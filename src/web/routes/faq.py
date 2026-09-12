from flask import Blueprint, render_template

faq_bp = Blueprint('faq', __name__)

@faq_bp.route('/faq')
def index():
    return render_template('faq.html')