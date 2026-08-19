from django.core.management.base import BaseCommand
from members.models import Family
from members.utils import heal_family_relations


class Command(BaseCommand):
    help = "Heal and synchronize family tree relationships for all families in the database"

    def handle(self, *args, **options):
        families = Family.objects.all()
        self.stdout.write(f"Starting family tree healing for {families.count()} families...")
        
        count = 0
        for family in families:
            heal_family_relations(family)
            count += 1
            
        self.stdout.write(self.style.SUCCESS(f"Successfully healed and synchronized {count} families."))
