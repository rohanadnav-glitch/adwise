from django.core.management.base import BaseCommand
from django.db import transaction
from apps.locations.models import State, District, City
from apps.categories.models import Category, SubCategory

class Command(BaseCommand):
    help = 'Seeds initial States, Districts, Cities, Categories, and SubCategories'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Starting master data seeding..."))

        # 1. Categories & Subcategories
        categories_data = {
            "Technology & Software": ["Web Development", "Data Science", "Mobile Apps", "Cybersecurity"],
            "Business & Legal": ["Corporate Law", "Taxation & Accounting", "Startup Advisory", "Marketing"],
            "Health & Fitness": ["Nutrition & Diet", "Mental Health", "Personal Training", "Yoga"],
            "Education & Career": ["Higher Studies", "Resume Review", "Interview Prep", "Competitive Exams"]
        }

        for cat_name, subcats in categories_data.items():
            category, _ = Category.objects.get_or_create(name=cat_name)
            for sub_name in subcats:
                SubCategory.objects.get_or_create(category=category, name=sub_name)

        # 2. Location Data
        locations_data = {
            "Maharashtra": {
                "Mumbai City": ["South Mumbai", "Andheri", "Bandra"],
                "Pune": ["Shivajinagar", "Kothrud", "Viman Nagar"],
                "Kolhapur": ["Karveer", "Kagal", "Gadhinglaj"]
            },
            "Karnataka": {
                "Bengaluru Urban": ["Indiranagar", "Koramangala", "Whitefield"],
                "Mysuru": ["Gokulam", "Vijayanagar"]
            },
            "Delhi": {
                "Central Delhi": ["Connaught Place", "Karol Bagh"],
                "South Delhi": ["Hauz Khas", "Saket"]
            }
        }

        for state_name, districts in locations_data.items():
            state, _ = State.objects.get_or_create(name=state_name)
            for dist_name, cities in districts.items():
                district, _ = District.objects.get_or_create(state=state, name=dist_name)
                for city_name in cities:
                    City.objects.get_or_create(district=district, name=city_name)

        self.stdout.write(self.style.SUCCESS("Master data seeded successfully!"))