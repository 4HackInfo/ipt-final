// Custom JavaScript for NSTP Attendance System

$(document).ready(function() {
    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        $('.alert').fadeOut('slow');
    }, 5000);
    
    // Form validation
    $('form').on('submit', function(e) {
        var requiredFields = $(this).find('[required]');
        var isValid = true;
        
        requiredFields.each(function() {
            if ($(this).val().trim() === '') {
                $(this).addClass('is-invalid');
                isValid = false;
            } else {
                $(this).removeClass('is-invalid');
            }
        });
        
        if (!isValid) {
            e.preventDefault();
            alert('Please fill in all required fields.');
        }
    });
    
    // Add loading state to buttons on click
    $('form button[type="submit"]').on('click', function() {
        var $btn = $(this);
        if ($btn.closest('form')[0].checkValidity()) {
            $btn.html('<i class="fas fa-spinner fa-spin"></i> Processing...');
            $btn.prop('disabled', true);
            $btn.closest('form').submit();
        }
    });
    
    // Confirm before important actions
    $('.confirm-action').on('click', function(e) {
        if (!confirm('Are you sure you want to perform this action?')) {
            e.preventDefault();
        }
    });
    
    // Select all functionality for checkboxes
    $('#select-all').on('change', function() {
        $('.student-checkbox').prop('checked', $(this).prop('checked'));
    });
    
    // Real-time clock display
    function updateClock() {
        var now = new Date();
        var dateTime = now.toLocaleString();
        $('#current-datetime').text(dateTime);
    }
    
    if ($('#current-datetime').length) {
        updateClock();
        setInterval(updateClock, 1000);
    }
    
    // Tooltip initialization
    $('[data-toggle="tooltip"]').tooltip();
    
    // Popover initialization
    $('[data-toggle="popover"]').popover();
});

$(document).ready(function() {
    $('#generateAgainBtn').on('click', function(e) {
        e.preventDefault();
        
        if (!confirm('Generate another batch of codes with the same settings?')) {
            return;
        }
        
        const $btn = $(this);
        const originalText = $btn.html();
        
        // Show loading state
        $btn.html('<i class="fas fa-spinner fa-spin"></i> Generating...');
        $btn.prop('disabled', true);
        
        $.ajax({
            url: '/generate-again-ajax/',
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            success: function(response) {
                if (response.success) {
                    // Reload the page to show new codes
                    window.location.reload();
                } else {
                    alert('Error: ' + response.message);
                    $btn.html(originalText);
                    $btn.prop('disabled', false);
                }
            },
            error: function(xhr) {
                alert('Error generating codes. Please try again.');
                $btn.html(originalText);
                $btn.prop('disabled', false);
            }
        });
    });
});

// Helper function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}