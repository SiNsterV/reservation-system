from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, DateField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Regexp
from datetime import datetime, time, timedelta

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

def generate_time_choices():
    times = []
    start = time(9, 0)  # 9:00 AM
    end = time(17, 0)   # 5:00 PM
    current = datetime.combine(datetime.today(), start)
    
    while current.time() <= end:
        t = current.time()
        times.append((t.strftime('%H:%M'), t.strftime('%H:%M')))
        current += timedelta(minutes=60)
    
    return times

def generate_block_time_choices():
    times = []
    start = time(9, 0)  # 9:00 AM
    end = time(17, 30)  # 5:30 PM
    current = datetime.combine(datetime.today(), start)
    
    while current.time() <= end:
        t = current.time()
        times.append((t.strftime('%H:%M'), t.strftime('%H:%M')))
        current += timedelta(minutes=60)
    
    return times


class AppointmentForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    time = SelectField('Time', 
                      choices=[('', 'Select time')] + generate_time_choices(), 
                      validators=[DataRequired()])
    service = SelectField('Service', coerce=int, validators=[DataRequired()])
    barber = SelectField('Barber', coerce=int, validators=[DataRequired()])
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone', validators=[
        DataRequired(),
        Length(min=9, max=9),
        Regexp(r'^\d{9}$', message='Phone number must be exactly 9 digits')
    ])
    notes = TextAreaField('Notes')
    submit = SubmitField('Book Appointment')
    


class BlockTimeForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    start_time = SelectField('Start Time', validators=[DataRequired()], 
                           choices=generate_block_time_choices())
    end_time = SelectField('End Time', validators=[DataRequired()], 
                          choices=generate_block_time_choices())
    reason = StringField('Reason', validators=[Length(max=200)])
    submit = SubmitField('Block Time')
    
class EmailUpdateForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(),
        Email(),
        Length(max=120)
    ])
    submit = SubmitField('Update Email')