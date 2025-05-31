document.addEventListener('DOMContentLoaded', function() {
    // Toggle between login and signup forms
    window.toggleForms = function() {
        document.querySelector('.login').classList.toggle('hidden');
        document.querySelector('.signup').classList.toggle('hidden');
    }

    // Show/Hide Password
    const togglePassword = function(inputField, toggleIcon) {
        if (inputField.type === 'password') {
            inputField.type = 'text';
            toggleIcon.classList.replace('fa-eye', 'fa-eye-slash');
        } else {
            inputField.type = 'password';
            toggleIcon.classList.replace('fa-eye-slash', 'fa-eye');
        }
    }

    // Form Validation
    const validateForm = function(formType) {
        const form = document.querySelector(`.${formType}`);
        const email = form.querySelector('input[type="email"]').value;
        const password = form.querySelector('input[type="password"]').value;

        // Basic email validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            showError('Please enter a valid email address');
            return false;
        }

        // Basic password validation
        if (password.length < 6) {
            showError('Password must be at least 6 characters long');
            return false;
        }

        // Additional signup validation
        if (formType === 'signup') {
            const name = form.querySelector('input[type="text"]').value;
            const confirmPassword = form.querySelectorAll('input[type="password"]')[1].value;

            if (name.length < 2) {
                showError('Please enter your full name');
                return false;
            }

            if (password !== confirmPassword) {
                showError('Passwords do not match');
                return false;
            }
        }

        return true;
    }

    // Show error message
    const showError = function(message) {
        const errorDiv = document.querySelector('.error-message');
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        setTimeout(() => {
            errorDiv.style.display = 'none';
        }, 3000);
    }

    // Form submission
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const formType = this.closest('.form-box').classList.contains('login') ? 'login' : 'signup';
            
            if (validateForm(formType)) {
                // Here you would typically make an API call to your backend
                console.log(`${formType} form submitted successfully`);
                // Example API call:
                // submitForm(formType, formData);
            }
        });
    });
});

// Example API call function
async function submitForm(formType, formData) {
    try {
        const response = await fetch(`/api/${formType}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });
        const data = await response.json();
        if (data.success) {
            // Handle successful login/signup
        } else {
            showError(data.message);
        }
    } catch (error) {
        showError('An error occurred. Please try again.');
    }
}