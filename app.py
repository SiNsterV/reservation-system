from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, time
import os
from flask import jsonify

from models import db, Barber, Customer, Service, Appointment, BlockedTime
from forms import LoginForm, AppointmentForm, BlockTimeForm

from flask import render_template
from flask_mail import Mail, Message



app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///barbershop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

mail = Mail(app)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Barber.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        barber = Barber.query.filter_by(username=form.username.data).first()
        if barber and check_password_hash(barber.password, form.password.data):
            login_user(barber)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

def send_booking_emails(booking, email_type='pending'):
    if email_type == 'pending':
        # Send pending confirmation to customer
        customer_msg = Message(
            'Booking Pending Confirmation',
            sender='vojjta99@gmail.com',
            recipients=[booking.customer.email]
        )
        customer_msg.html = render_template('emails/book_pending.html', booking=booking)
        mail.send(customer_msg)

        # Send notification to barber
        barber_msg = Message(
            'New Booking Request',
            sender='vojjta99@gmail.com',
            recipients=[booking.barber.email]
        )
        barber_msg.html = render_template('emails/book_alert.html', booking=booking)
        mail.send(barber_msg)
    
    elif email_type == 'confirmed':
        # Send confirmation to customer
        customer_msg = Message(
            'Appointment Confirmed',
            sender='vojjta99@gmail.com',
            recipients=[booking.customer.email]
        )
        customer_msg.html = render_template('emails/book_conf.html', booking=booking)
        mail.send(customer_msg)
    elif email_type == "cancelled":
        customer_msg = Message(
            'Appointment Cancelled',
            #tood
        )

# ...existing code...

@app.route('/gallery')
def gallery():
    # You can add these sample gallery items or load them from a database
    gallery_items = [
        {
            'image_url': '/static/images/cut1.webp',
            'title': 'Classic Cut',
            'description': 'Traditional men\'s haircut with precise fading'
        },
        {
            'image_url': '/static/images/cut2.jpg',
            'title': 'Modern Style',
            'description': 'Contemporary styling with textured finish'
        },
        # Add more items as needed
    ]
    return render_template('gallery.html', gallery_items=gallery_items)

@app.route('/book', methods=['GET', 'POST'])
def book():
    form = AppointmentForm()
    form.barber.choices = [(b.id, b.name) for b in Barber.query.all()]
    form.service.choices = [(s.id, f"{s.name} (${s.price:.2f})") for s in Service.query.all()]
    
    if form.validate_on_submit():
        try:
            # Convert time string to time object
            hour, minute = map(int, form.time.data.split(':'))
            appointment_time = time(hour, minute)
            
            # Check if time is available
            selected_date = form.date.data
            barber_id = form.barber.data
            
            # Check existing appointments
            existing_appointment = Appointment.query.filter_by(
                date=selected_date,
                time=appointment_time,
                barber_id=barber_id,
                status='confirmed'
            ).first()
            
            # Check blocked times
            blocked_time = BlockedTime.query.filter(
                BlockedTime.date == selected_date,
                BlockedTime.barber_id == barber_id,
                BlockedTime.start_time <= appointment_time,
                BlockedTime.end_time >= appointment_time
            ).first()
            
            if existing_appointment or blocked_time:
                flash('This time slot is no longer available. Please select another time.')
                return render_template('book.html', form=form)
            
            # Create customer first
            customer = Customer(
                name=form.name.data,
                email=form.email.data,
                phone=form.phone.data
            )
            db.session.add(customer)
            db.session.flush()  # This assigns an ID to the customer
            
            # Create appointment with all required data
            appointment = Appointment(
                date=form.date.data,
                time=appointment_time,
                barber_id=form.barber.data,
                service_id=form.service.data,
                customer=customer,
                notes=form.notes.data
            )
            db.session.add(appointment)
            db.session.commit()
            
            # Send confirmation emails
            send_booking_emails(appointment, email_type='pending')
            
            flash('Booking submitted! Check your email for confirmation.')
            return redirect(url_for('index'))
            
        except Exception as e:
            db.session.rollback()
            flash('Error booking appointment. Please try again.')
            print(f"Booking error: {str(e)}")
    
    return render_template('book.html', form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    today = datetime.now().date()
    current_time = datetime.now().time()
    
    past_appointments = Appointment.query.filter_by(
        barber=current_user, 
        status='confirmed'
    ).filter(
        (Appointment.date < today) | 
        ((Appointment.date == today) & (Appointment.time < current_time))
    ).all()
    
    for appointment in past_appointments:
        appointment.status = 'completed'
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error auto-completing appointments: {str(e)}")
    
    # Get appointments for display
    appointments = Appointment.query.filter_by(barber=current_user)\
        .filter(Appointment.date >= today)\
        .order_by(Appointment.date, Appointment.time).all()
        
    # Get blocked times
    blocked_times = BlockedTime.query.filter_by(barber_id=current_user.id)\
        .filter(BlockedTime.date >= today)\
        .order_by(BlockedTime.date, BlockedTime.start_time).all()
    
    return render_template('dashboard.html', 
                         appointments=appointments, 
                         blocked_times=blocked_times)
    
@app.route('/delete-block/<int:id>', methods=['POST'])
@login_required
def delete_block(id):
    if not isinstance(current_user, Barber):
        flash('Access denied')
        return redirect(url_for('index'))
    
    block = BlockedTime.query.get_or_404(id)
    if block.barber_id != current_user.id:
        flash('Access denied')
        return redirect(url_for('dashboard'))
    
    try:
        db.session.delete(block)
        db.session.commit()
        flash('Blocked time removed successfully!')
    except Exception as e:
        db.session.rollback()
        flash('Error removing blocked time')
        print(f"Block deletion error: {str(e)}")
    
    return redirect(url_for('dashboard'))

@app.route('/block-time', methods=['GET', 'POST'])
@login_required
def block_time():
    form = BlockTimeForm()
    if form.validate_on_submit():
        # Convert time strings to time objects
        start_hour, start_minute = map(int, form.start_time.data.split(':'))
        end_hour, end_minute = map(int, form.end_time.data.split(':'))
        
        blocked_time = BlockedTime(
            barber_id=current_user.id,
            date=form.date.data,
            start_time=time(start_hour, start_minute),
            end_time=time(end_hour, end_minute),
            reason=form.reason.data
        )
        db.session.add(blocked_time)
        try:
            db.session.commit()
            flash('Time blocked successfully!')
            return redirect(url_for('dashboard'))
        except:
            db.session.rollback()
            flash('Error blocking time. Please try again.')
    
    return render_template('block_time.html', form=form)

@app.route('/update_appointment_status/<int:id>', methods=['POST'])
@login_required
def update_appointment_status(id):
    if not isinstance(current_user, Barber):
        flash('Access denied')
        return redirect(url_for('index'))
    
    appointment = Appointment.query.get_or_404(id)
    new_status = request.form.get('status')
    
    if new_status in ['pending', 'confirmed', 'completed', 'cancelled']:
        old_status = appointment.status
        appointment.status = new_status
        
        try:
            db.session.commit()
            
            # Send confirmation email when status changes to confirmed
            if old_status == 'pending' and new_status == 'confirmed':
                send_booking_emails(appointment, email_type='confirmed')
            
            flash(f'Appointment status updated to {new_status}')
            flash("Confirmation email sent to customer")
        except Exception as e:
            db.session.rollback()
            flash('Error updating appointment status')
            print(f"Status update error: {str(e)}")
    
    return redirect(url_for('dashboard'))

@app.route('/update_email', methods=['POST'])
@login_required
def update_email():
    if not isinstance(current_user, Barber):
        flash('Access denied')
        return redirect(url_for('index'))
    
    new_email = request.form.get('email')
    if new_email:
        try:
            current_user.email = new_email
            db.session.commit()
            flash('Email updated successfully!')
        except Exception as e:
            db.session.rollback()
            flash('Error updating email')
            print(f"Email update error: {str(e)}")
    
    return redirect(url_for('dashboard'))

@app.route('/cleanup_appointments', methods=['POST'])
@login_required
def cleanup_appointments():
    if not isinstance(current_user, Barber):
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        # Delete completed and cancelled appointments
        Appointment.query.filter(
            Appointment.barber == current_user,
            Appointment.status.in_(['completed', 'cancelled'])
        ).delete(synchronize_session=False)
        
        db.session.commit()
        flash('Old appointments cleaned up successfully!')
    except Exception as e:
        db.session.rollback()
        flash('Error cleaning up appointments')
        print(f"Cleanup error: {str(e)}")
    
    return redirect(url_for('dashboard'))

# Add this import at the top
from flask import jsonify

# Add this new route before if __name__ == '__main__':
@app.route('/get-available-times', methods=['GET'])
def get_available_times():
    date = request.args.get('date')
    barber_id = request.args.get('barber_id')
    
    if not date or not barber_id:
        return jsonify({'error': 'Missing parameters'}), 400
    
    try:
        selected_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Get all appointments for this date and barber
        booked_times = Appointment.query.filter_by(
            date=selected_date,
            barber_id=barber_id
        ).filter(
            Appointment.status.in_(['pending', 'confirmed'])  # Include both pending and confirmed
        ).with_entities(Appointment.time).all()
        
        # Get blocked times
        blocked_times = BlockedTime.query.filter_by(
            date=selected_date,
            barber_id=barber_id
        ).all()
        
        # Convert booked times to list of strings
        unavailable_times = [t[0].strftime('%H:%M') for t in booked_times]
        
        # Add all times within blocked periods
        for block in blocked_times:
            current_time = block.start_time
            while current_time <= block.end_time:
                time_str = current_time.strftime('%H:%M')
                if time_str not in unavailable_times:
                    unavailable_times.append(time_str)
                # Increment by 30 minutes
                current_datetime = datetime.combine(selected_date, current_time)
                current_datetime += timedelta(minutes=30)
                current_time = current_datetime.time()
        
        return jsonify({'booked_times': unavailable_times})
    
    except Exception as e:
        print(f"Error getting available times: {str(e)}")



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 
    
    