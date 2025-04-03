from flask import Flask, render_template, redirect, url_for, flash, request, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, time
import os
from flask import jsonify

from models import db, Barber, Customer, Service, Appointment, BlockedTime
from forms import LoginForm, AppointmentForm, BlockTimeForm

from flask import render_template
from flask_mail import Mail, Message



app = Flask(__name__, static_url_path='/static')
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

@app.route('/booking-confirmed')
def booking_confirmed():
    # Get the latest booking for the user from session
    booking_id = session.get('last_booking_id')
    if not booking_id:
        return redirect(url_for('index'))
    
    booking = Appointment.query.filter_by(id=booking_id)\
        .join(Customer)\
        .join(Service)\
        .join(Barber)\
        .first()
        
    if not booking:
        flash('Booking not found', 'error')
        return redirect(url_for('index'))
    
    # Format the data for display
    booking_data = {
        'email': booking.customer.email,
        'service': booking.service.name,
        'barber': booking.barber.name,
        'date': booking.date.strftime('%B %d, %Y'),
        'time': booking.time.strftime('%I:%M %p'),
        'reference': f'BK{booking.id:06d}'
    }
    
    return render_template('booking_confirmed.html', booking=booking_data)

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
    if request.method == 'GET':
        form = AppointmentForm()
        form.barber.choices = [(b.id, b.name) for b in Barber.query.all()]
        form.service.choices = [(s.id, f"{s.name} (${s.price:.2f})") for s in Service.query.all()]
        return render_template('book.html', form=form)
        
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            email = request.form.get('email')
            phone = request.form.get('phone')
            date_str = request.form.get('date')
            time_str = request.form.get('time')
            barber_id = int(request.form.get('barber_id'))
            service_id = int(request.form.get('service_id'))
            notes = request.form.get('notes', '')

            # Convert date and time strings to proper formats
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            hour, minute = map(int, time_str.split(':'))
            appointment_time = time(hour, minute)

            # Check availability
            is_available = check_availability(date, appointment_time, barber_id)
            if not is_available:
                return jsonify({
                    'status': 'error',
                    'message': 'This time slot is no longer available'
                }), 400

            # Create customer
            customer = Customer(
                name=name,
                email=email,
                phone=phone
            )
            db.session.add(customer)
            db.session.flush()

            # Create appointment
            appointment = Appointment(
                date=date,
                time=appointment_time,
                barber_id=barber_id,
                service_id=service_id,
                customer=customer,
                notes=notes
            )
            db.session.add(appointment)
            db.session.commit()

            # Send confirmation emails
            send_booking_emails(appointment, email_type='pending')

            session['last_booking_id'] = appointment.id
        
            return jsonify({
                'status': 'success',
                'message': 'Booking confirmed!'
            })

        except Exception as e:
            db.session.rollback()
            print(f"Booking error: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Error processing booking'
            }), 500

def check_availability(date, time, barber_id):
    """Check if the time slot is available"""
    existing_appointment = Appointment.query.filter_by(
        date=date,
        time=time,
        barber_id=barber_id,
        status='confirmed'
    ).first()
    
    blocked_time = BlockedTime.query.filter(
        BlockedTime.date == date,
        BlockedTime.barber_id == barber_id,
        BlockedTime.start_time <= time,
        BlockedTime.end_time >= time
    ).first()
    
    return not (existing_appointment or blocked_time)

def create_appointment(date, time, barber_id, service_id, customer_name, 
                      customer_email, customer_phone, notes=None):
    """Create a new appointment with customer"""
    try:
        # Create customer first
        customer = Customer(
            name=customer_name,
            email=customer_email,
            phone=customer_phone
        )
        db.session.add(customer)
        db.session.flush()
        
        # Create appointment
        appointment = Appointment(
            date=date,
            time=time,
            barber_id=barber_id,
            service_id=service_id,
            customer=customer,
            notes=notes
        )
        db.session.add(appointment)
        db.session.commit()
        
        # Send confirmation emails
        send_booking_emails(appointment, email_type='pending')
        
        return appointment
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating appointment: {str(e)}")
        return None

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

@app.route('/get-available-times')
def get_available_times():
    date = request.args.get('date')
    barber_id = request.args.get('barber_id')
    service_id = request.args.get('service_id')

    if not all([date, barber_id, service_id]):
        return jsonify({'error': 'Missing required parameters'}), 400

    try:
        # Convert date string to date object
        booking_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Get service duration
        service = Service.query.get(service_id)
        if not service:
            return jsonify({'error': 'Service not found'}), 404
            
        service_duration = service.duration  # in minutes

        # Get all bookings for this barber on this date
        booked_slots = Appointment.query.filter(
            Appointment.barber_id == barber_id,
            Appointment.date == booking_date,
            Appointment.status != 'cancelled'
        ).all()

        # Get blocked times for this barber
        blocked_times = BlockedTime.query.filter(
            BlockedTime.barber_id == barber_id,
            BlockedTime.date == booking_date
        ).all()

        # Calculate unavailable time slots
        booked_times = set()
        
        for booking in booked_slots:
            # Block the booked time and subsequent slots based on service duration
            start_time = booking.time
            end_time = (datetime.combine(booking_date, start_time) + 
                       timedelta(minutes=booking.service.duration)).time()
            
            current = start_time
            while current < end_time:
                booked_times.add(current.strftime('%H:%M'))
                current = (datetime.combine(booking_date, current) + 
                          timedelta(minutes=30)).time()

        # Add blocked times
        for block in blocked_times:
            start_time = block.start_time
            end_time = block.end_time
            
            current = start_time
            while current < end_time:
                booked_times.add(current.strftime('%H:%M'))
                current = (datetime.combine(booking_date, current) + 
                          timedelta(minutes=30)).time()

        return jsonify({
            'booked_times': sorted(list(booked_times)),
            'service_duration': service_duration
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 
    
    