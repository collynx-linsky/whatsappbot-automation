"""WhatsAppBusinessAI — Knowledge Base Celery Tasks"""

import logging

from celery import shared_task

logger = logging.getLogger("waba")


@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def process_knowledge_document_task(self, document_id: str):
    """Extracts, chunks, and (if a provider is configured) embeds one KnowledgeDocument."""
    from apps.knowledge.models import KnowledgeDocument
    from apps.knowledge.services import process_document

    try:
        document = KnowledgeDocument.objects.select_related("business").get(pk=document_id)
    except KnowledgeDocument.DoesNotExist:
        logger.warning(
            "process_knowledge_document_task: document %s no longer exists.", document_id
        )
        return

    process_document(document)
