from django.core.management.base import BaseCommand
from django.utils import timezone
from core.utils import reset_slip_codes_weekly

class Command(BaseCommand):
    help = 'Reset expired slip codes weekly'
    
    def handle(self, *args, **options):
        reset_slip_codes_weekly()
        self.stdout.write(self.style.SUCCESS('Successfully reset expired slip codes'))