from django.core.management.base import BaseCommand
from contextbridge_app.services.knowledge_services import ClaudeExtractionService


class Command(BaseCommand):
    help = 'Verify Anthropic API connectivity (models list only, no content sent)'

    def handle(self, *args, **options):
        svc = ClaudeExtractionService()
        if not svc.available:
            self.stdout.write(self.style.WARNING('No Anthropic API key configured or client failed to init.'))
            return
        models = svc.list_models()
        if models:
            self.stdout.write(self.style.SUCCESS(f'Connected. Models available: {len(models)}'))
            for m in models[:5]:
                self.stdout.write(f'  - {m}')
        else:
            self.stdout.write(self.style.ERROR('Key present but models.list() returned empty or failed.'))
