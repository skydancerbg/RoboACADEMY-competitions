from django import forms
from django.contrib.auth.models import User
from django.shortcuts import render, redirect

from .models import UserProfile


class RegistrationForm(forms.Form):
    username       = forms.CharField(max_length=150)
    first_name     = forms.CharField(max_length=150)
    last_name      = forms.CharField(max_length=150)
    email          = forms.EmailField()
    password       = forms.CharField(widget=forms.PasswordInput)
    password2      = forms.CharField(widget=forms.PasswordInput, label='Confirm password')
    requested_role = forms.ChoiceField(choices=[('judge', 'Judge'), ('organiser', 'Organiser')])
    organisation   = forms.CharField(max_length=200, required=False)
    country        = forms.CharField(max_length=100, required=False)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('password2'):
            raise forms.ValidationError('Passwords do not match.')
        return cleaned


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            user = User.objects.create_user(
                username   = d['username'],
                email      = d['email'],
                password   = d['password'],
                first_name = d['first_name'],
                last_name  = d['last_name'],
                is_active  = False,
            )
            UserProfile.objects.create(
                user           = user,
                requested_role = d['requested_role'],
                organisation   = d['organisation'],
                country        = d['country'],
            )
            return redirect('contest:register_pending')
    else:
        form = RegistrationForm()
    return render(request, 'contest/register.html', {'form': form})


def register_pending(request):
    return render(request, 'contest/register_pending.html')
