"""
Comprehensive test suite for Extraction Service
Tests: models, CRUD, services, extractors, routes, and edge cases
"""

import pytest
import pytest_asyncio
import tempfile
import json
import csv
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from src.shared.db import Base
from src.shared.config import Settings
from src.file_service.models import Tenant, File
from src.extraction_service.models import ExtractionResult
from src.extraction_service.schemas import (
    ExtractionRequest, ExtractionUpdate, ExtractionSearchRequest,
    BulkExtractionRequest, RetryExtractionRequest, ExtractionConfig,
    ExtractionType, ExtractionStatus
)
from src.extraction_service.crud import ExtractionCRUD
from src.extraction_service.services import (
    ExtractionService, FileExtractor, TextExtractor,
    MetadataExtractor, StructuredDataExtractor
)


# Test Database Setup
@pytest_asyncio.fixture
async def async_session():
    """Create test database session"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session_maker() as session:
        yield session
    
    await engine.dispose()


@pytest_asyncio.fixture
async def mock_redis():
    """Mock Redis client"""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = True
    mock_redis.exists.return_value = False
    return mock_redis


@pytest_asyncio.fixture
async def test_settings():
    """Test configuration settings"""
    return Settings(
        storage_base_path="/tmp/test_storage",
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/1"
    )


@pytest_asyncio.fixture
async def temp_storage():
    """Create temporary storage directory"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest_asyncio.fixture
async def sample_tenant(async_session):
    """Create a sample tenant for testing"""
    tenant = Tenant(
        code="test123",
        name="Test Tenant",
        description="Test tenant for extraction tests"
    )
    async_session.add(tenant)
    await async_session.commit()
    await async_session.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def sample_file(async_session, sample_tenant, temp_storage):
    """Create a sample file for testing"""
    file_path = f"{temp_storage}/test_file.txt"
    Path(file_path).write_text("This is test file content for extraction.")
    
    file = File(
        tenant_id=sample_tenant.id,
        tenant_code=sample_tenant.code,
        original_filename="test_file.txt",
        stored_filename="stored_test_file.txt",
        file_path=file_path,
        file_size=42,
        mime_type="text/plain",
        file_extension=".txt",
        file_hash="test_hash_123"
    )
    async_session.add(file)
    await async_session.commit()
    await async_session.refresh(file)
    return file


# Model Tests
@pytest.mark.unit
class TestExtractionResultModel:
    """Test ExtractionResult model functionality"""
    
    def test_extraction_result_creation(self):
        """Test basic extraction result creation"""
        result = ExtractionResult(
            file_id=uuid4(),
            tenant_id=uuid4(),
            extraction_type=ExtractionType.TEXT,
            status=ExtractionStatus.PENDING,
            extractor_version="1.0.0",
            progress_percentage=0
        )
        
        assert result.extraction_type == ExtractionType.TEXT
        assert result.status == ExtractionStatus.PENDING
        assert result.progress_percentage == 0
        assert result.extractor_version == "1.0.0"
    
    def test_extraction_result_properties(self):
        """Test extraction result computed properties"""
        result = ExtractionResult(
            file_id=uuid4(),
            tenant_id=uuid4(),
            extraction_type=ExtractionType.FULL,
            status=ExtractionStatus.COMPLETED,
            confidence_score=0.95,
            processing_time_ms=1500
        )
        
        assert result.is_completed is True
        assert result.is_failed is False
        assert result.is_processing is False
        assert result.can_retry is False
    
    def test_extraction_result_failed_state(self):
        """Test extraction result in failed state"""
        result = ExtractionResult(
            file_id=uuid4(),
            tenant_id=uuid4(),
            extraction_type=ExtractionType.TEXT,
            status=ExtractionStatus.FAILED,
            error_message="Processing failed",
            retry_count=2,
            max_retries=3
        )
        
        assert result.is_failed is True
        assert result.can_retry is True
    
    def test_processing_summary(self):
        """Test processing summary generation"""
        result = ExtractionResult(
            file_id=uuid4(),
            tenant_id=uuid4(),
            extraction_type=ExtractionType.METADATA,
            status=ExtractionStatus.COMPLETED,
            confidence_score=0.88,
            processing_time_ms=2500,
            memory_usage_mb=15.5
        )
        
        summary = result.get_processing_summary()
        assert summary["status"] == "completed"
        assert summary["confidence_score"] == 0.88
        assert summary["processing_time_ms"] == 2500
        assert summary["memory_usage_mb"] == 15.5


# CRUD Tests
@pytest.mark.unit
class TestExtractionCRUD:
    """Test ExtractionCRUD operations"""
    
    @pytest.mark.asyncio
    async def test_create_extraction(self, async_session, sample_file, mock_redis):
        """Test extraction result creation"""
        crud = ExtractionCRUD()
        extraction_data = {
            "file_id": sample_file.id,
            "tenant_id": sample_file.tenant_id,
            "extraction_type": ExtractionType.TEXT,
            "status": ExtractionStatus.PENDING,
            "extractor_version": "1.0.0"
        }
        
        extraction = await crud.create(async_session, extraction_data, mock_redis)
        
        assert extraction.file_id == sample_file.id
        assert extraction.extraction_type == ExtractionType.TEXT
        assert extraction.status == ExtractionStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_get_extraction_by_id(self, async_session, sample_file, mock_redis):
        """Test getting extraction by ID"""
        crud = ExtractionCRUD()
        
        # Create extraction
        extraction_data = {
            "file_id": sample_file.id,
            "tenant_id": sample_file.tenant_id,
            "extraction_type": ExtractionType.METADATA,
            "status": ExtractionStatus.PROCESSING
        }
        created = await crud.create(async_session, extraction_data, mock_redis)
        
        # Get by ID
        retrieved = await crud.get_by_id(async_session, created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.file is not None  # Should load related file
    
    @pytest.mark.asyncio
    async def test_get_extractions_by_file(self, async_session, sample_file, mock_redis):
        """Test getting extractions by file ID"""
        crud = ExtractionCRUD()
        
        # Create multiple extractions for the same file
        extraction_types = [ExtractionType.TEXT, ExtractionType.METADATA, ExtractionType.STRUCTURED_DATA]
        
        for ext_type in extraction_types:
            extraction_data = {
                "file_id": sample_file.id,
                "tenant_id": sample_file.tenant_id,
                "extraction_type": ext_type,
                "status": ExtractionStatus.COMPLETED
            }
            await crud.create(async_session, extraction_data, mock_redis)
        
        # Get extractions by file
        extractions = await crud.get_by_file_id(async_session, sample_file.id)
        
        assert len(extractions) == 3
        assert all(e.file_id == sample_file.id for e in extractions)
    
    @pytest.mark.asyncio
    async def test_search_extractions(self, async_session, sample_file, mock_redis):
        """Test extraction search functionality"""
        crud = ExtractionCRUD()
        
        # Create extractions with different statuses
        extractions_data = [
            {
                "file_id": sample_file.id,
                "tenant_id": sample_file.tenant_id,
                "extraction_type": ExtractionType.TEXT,
                "status": ExtractionStatus.COMPLETED,
                "confidence_score": 0.95
            },
            {
                "file_id": sample_file.id,
                "tenant_id": sample_file.tenant_id,
                "extraction_type": ExtractionType.METADATA,
                "status": ExtractionStatus.FAILED
            }
        ]
        
        for data in extractions_data:
            await crud.create(async_session, data, mock_redis)
        
        # Search for completed extractions
        search_request = ExtractionSearchRequest(
            tenant_id=sample_file.tenant_id,
            status=ExtractionStatus.COMPLETED,
            extraction_type=ExtractionType.TEXT,
            min_confidence=0.9
        )
        
        results, total = await crud.search_extractions(async_session, search_request)
        
        assert len(results) == 1
        assert results[0].status == ExtractionStatus.COMPLETED
        assert results[0].extraction_type == ExtractionType.TEXT
    
    @pytest.mark.asyncio
    async def test_update_extraction(self, async_session, sample_file, mock_redis):
        """Test extraction update"""
        crud = ExtractionCRUD()
        
        # Create extraction
        extraction_data = {
            "file_id": sample_file.id,
            "tenant_id": sample_file.tenant_id,
            "extraction_type": ExtractionType.TEXT,
            "status": ExtractionStatus.PROCESSING,
            "progress_percentage": 0
        }
        extraction = await crud.create(async_session, extraction_data, mock_redis)
        
        # Update extraction
        update_data = {
            "status": ExtractionStatus.COMPLETED,
            "progress_percentage": 100,
            "extracted_text": "Extracted text content",
            "confidence_score": 0.92,
            "processing_time_ms": 1200
        }
        
        updated = await crud.update(async_session, extraction.id, update_data, mock_redis)
        
        assert updated.status == ExtractionStatus.COMPLETED
        assert updated.progress_percentage == 100
        assert updated.extracted_text == "Extracted text content"
        assert updated.confidence_score == 0.92
        assert updated.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_get_pending_extractions(self, async_session, sample_file, mock_redis):
        """Test getting pending extractions"""
        crud = ExtractionCRUD()
        
        # Create extractions with different statuses
        statuses = [ExtractionStatus.PENDING, ExtractionStatus.PROCESSING, ExtractionStatus.COMPLETED]
        
        for status in statuses:
            extraction_data = {
                "file_id": sample_file.id,
                "tenant_id": sample_file.tenant_id,
                "extraction_type": ExtractionType.TEXT,
                "status": status
            }
            await crud.create(async_session, extraction_data, mock_redis)
        
        # Get pending extractions
        pending = await crud.get_pending_extractions(async_session, limit=10)
        
        assert len(pending) == 1
        assert pending[0].status == ExtractionStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_get_extraction_stats(self, async_session, sample_file, mock_redis):
        """Test extraction statistics"""
        crud = ExtractionCRUD()
        
        # Create extractions with different outcomes
        extractions_data = [
            {"status": ExtractionStatus.COMPLETED, "confidence_score": 0.95},
            {"status": ExtractionStatus.COMPLETED, "confidence_score": 0.88},
            {"status": ExtractionStatus.FAILED},
            {"status": ExtractionStatus.PENDING}
        ]
        
        for data in extractions_data:
            extraction_data = {
                "file_id": sample_file.id,
                "tenant_id": sample_file.tenant_id,
                "extraction_type": ExtractionType.TEXT,
                **data
            }
            await crud.create(async_session, extraction_data, mock_redis)
        
        # Get stats
        stats = await crud.get_extraction_stats(async_session)
        
        assert stats["total_extractions"] == 4
        assert stats["completed_extractions"] == 2
        assert stats["failed_extractions"] == 1
        assert stats["pending_extractions"] == 1


# Extractor Tests
@pytest.mark.unit
class TestFileExtractors:
    """Test individual file extractors"""
    
    @pytest.mark.asyncio
    async def test_text_extractor_txt_file(self, temp_storage):
        """Test text extraction from txt file"""
        extractor = TextExtractor()
        
        # Create test file
        file_path = f"{temp_storage}/test.txt"
        test_content = "This is a test document.\nIt has multiple lines.\nAnd some special characters: àáâã"
        Path(file_path).write_text(test_content, encoding='utf-8')
        
        # Extract text
        result = await extractor.extract(file_path, {"encoding": "utf-8"})
        
        assert result["success"] is True
        assert result["extracted_text"] == test_content
        assert "metadata" in result
        assert result["metadata"]["file_size"] > 0
    
    @pytest.mark.asyncio
    async def test_text_extractor_json_file(self, temp_storage):
        """Test text extraction from JSON file"""
        extractor = TextExtractor()
        
        # Create test JSON file
        file_path = f"{temp_storage}/test.json"
        json_data = {
            "title": "Test Document",
            "content": "This is JSON content",
            "metadata": {"author": "Test Author", "date": "2024-01-01"}
        }
        Path(file_path).write_text(json.dumps(json_data, indent=2))
        
        # Extract text
        result = await extractor.extract(file_path, {})
        
        assert result["success"] is True
        assert "Test Document" in result["extracted_text"]
        assert "This is JSON content" in result["extracted_text"]
    
    @pytest.mark.asyncio
    async def test_text_extractor_csv_file(self, temp_storage):
        """Test text extraction from CSV file"""
        extractor = TextExtractor()
        
        # Create test CSV file
        file_path = f"{temp_storage}/test.csv"
        with open(file_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Name', 'Age', 'City'])
            writer.writerow(['John Doe', '30', 'New York'])
            writer.writerow(['Jane Smith', '25', 'Los Angeles'])
        
        # Extract text
        result = await extractor.extract(file_path, {})
        
        assert result["success"] is True
        assert "Name,Age,City" in result["extracted_text"]
        assert "John Doe" in result["extracted_text"]
    
    @pytest.mark.asyncio
    async def test_metadata_extractor(self, temp_storage):
        """Test metadata extraction"""
        extractor = MetadataExtractor()
        
        # Create test file
        file_path = f"{temp_storage}/test_meta.txt"
        Path(file_path).write_text("Test content for metadata extraction")
        
        # Extract metadata
        result = await extractor.extract(file_path, {})
        
        assert result["success"] is True
        assert "file_stats" in result["metadata"]
        assert "format_metadata" in result["metadata"]
        
        file_stats = result["metadata"]["file_stats"]
        assert file_stats["size"] > 0
        assert file_stats["extension"] == ".txt"
    
    @pytest.mark.asyncio
    async def test_structured_data_extractor_json(self, temp_storage):
        """Test structured data extraction from JSON"""
        extractor = StructuredDataExtractor()
        
        # Create test JSON file with nested structure
        file_path = f"{temp_storage}/structured.json"
        json_data = {
            "users": [
                {"id": 1, "name": "John", "email": "john@example.com"},
                {"id": 2, "name": "Jane", "email": "jane@example.com"}
            ],
            "metadata": {
                "total_count": 2,
                "last_updated": "2024-01-01T00:00:00Z"
            }
        }
        Path(file_path).write_text(json.dumps(json_data))
        
        # Extract structured data
        result = await extractor.extract(file_path, {})
        
        assert result["success"] is True
        assert "structured_data" in result
        assert "schema_analysis" in result
        
        structured_data = result["structured_data"]
        assert "users" in structured_data
        assert len(structured_data["users"]) == 2
    
    @pytest.mark.asyncio
    async def test_structured_data_extractor_csv(self, temp_storage):
        """Test structured data extraction from CSV"""
        extractor = StructuredDataExtractor()
        
        # Create test CSV file
        file_path = f"{temp_storage}/structured.csv"
        with open(file_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['ID', 'Name', 'Score', 'Date'])
            writer.writerow(['1', 'Alice', '95.5', '2024-01-01'])
            writer.writerow(['2', 'Bob', '87.2', '2024-01-02'])
            writer.writerow(['3', 'Charlie', '92.8', '2024-01-03'])
        
        # Extract structured data
        result = await extractor.extract(file_path, {})
        
        assert result["success"] is True
        assert "structured_data" in result
        assert "column_analysis" in result
        
        structured_data = result["structured_data"]
        assert len(structured_data) == 3  # 3 data rows
        assert structured_data[0]["Name"] == "Alice"
        
        column_analysis = result["column_analysis"]
        assert "ID" in column_analysis
        assert column_analysis["Score"]["inferred_type"] == "float"
    
    @pytest.mark.asyncio
    async def test_extractor_error_handling(self, temp_storage):
        """Test extractor error handling"""
        extractor = TextExtractor()
        
        # Test with nonexistent file
        result = await extractor.extract("/nonexistent/file.txt", {})
        
        assert result["success"] is False
        assert "error" in result
        assert "FileNotFoundError" in result["error"] or "No such file" in result["error"]


# Service Tests
@pytest.mark.unit
class TestExtractionService:
    """Test ExtractionService business logic"""
    
    @pytest.mark.asyncio
    async def test_request_extraction(self, async_session, sample_file, mock_redis):
        """Test extraction request creation"""
        service = ExtractionService()
        
        request = ExtractionRequest(
            file_id=sample_file.id,
            tenant_id=sample_file.tenant_id,
            extraction_type=ExtractionType.TEXT,
            config=ExtractionConfig(
                include_metadata=True,
                confidence_threshold=0.8
            )
        )
        
        extraction = await service.request_extraction(async_session, request, mock_redis)
        
        assert extraction.file_id == sample_file.id
        assert extraction.extraction_type == ExtractionType.TEXT
        assert extraction.status == ExtractionStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_process_extraction_text(self, async_session, sample_file, mock_redis, temp_storage):
        """Test text extraction processing"""
        service = ExtractionService()
        
        # Create extraction request
        request = ExtractionRequest(
            file_id=sample_file.id,
            tenant_id=sample_file.tenant_id,
            extraction_type=ExtractionType.TEXT
        )
        extraction = await service.request_extraction(async_session, request, mock_redis)
        
        # Process extraction
        result = await service.process_extraction(async_session, extraction.id, mock_redis)
        
        assert result is not None
        assert result.status == ExtractionStatus.COMPLETED
        assert result.extracted_text is not None
        assert result.processing_time_ms > 0
    
    @pytest.mark.asyncio
    async def test_process_extraction_metadata(self, async_session, sample_file, mock_redis):
        """Test metadata extraction processing"""
        service = ExtractionService()
        
        # Create extraction request
        request = ExtractionRequest(
            file_id=sample_file.id,
            tenant_id=sample_file.tenant_id,
            extraction_type=ExtractionType.METADATA
        )
        extraction = await service.request_extraction(async_session, request, mock_redis)
        
        # Process extraction
        result = await service.process_extraction(async_session, extraction.id, mock_redis)
        
        assert result is not None
        assert result.status == ExtractionStatus.COMPLETED
        assert result.metadata is not None
        metadata = json.loads(result.metadata)
        assert "file_stats" in metadata
    
    @pytest.mark.asyncio
    async def test_process_extraction_full(self, async_session, sample_file, mock_redis):
        """Test full extraction processing"""
        service = ExtractionService()
        
        # Create extraction request
        request = ExtractionRequest(
            file_id=sample_file.id,
            tenant_id=sample_file.tenant_id,
            extraction_type=ExtractionType.FULL
        )
        extraction = await service.request_extraction(async_session, request, mock_redis)
        
        # Process extraction
        result = await service.process_extraction(async_session, extraction.id, mock_redis)
        
        assert result is not None
        assert result.status == ExtractionStatus.COMPLETED
        assert result.extracted_text is not None
        assert result.metadata is not None
        assert result.structured_data is not None
    
    @pytest.mark.asyncio
    async def test_bulk_request_extractions(self, async_session, sample_file, mock_redis):
        """Test bulk extraction requests"""
        service = ExtractionService()
        
        bulk_request = BulkExtractionRequest(
            file_ids=[sample_file.id],
            tenant_id=sample_file.tenant_id,
            extraction_types=[ExtractionType.TEXT, ExtractionType.METADATA],
            config=ExtractionConfig(
                include_metadata=True,
                confidence_threshold=0.7
            )
        )
        
        extractions = await service.bulk_request_extractions(async_session, bulk_request, mock_redis)
        
        assert len(extractions) == 2  # One for each extraction type
        assert all(e.file_id == sample_file.id for e in extractions)
        assert {e.extraction_type for e in extractions} == {ExtractionType.TEXT, ExtractionType.METADATA}
    
    @pytest.mark.asyncio
    async def test_retry_extractions(self, async_session, sample_file, mock_redis):
        """Test extraction retry functionality"""
        service = ExtractionService()
        
        # Create failed extraction
        crud = ExtractionCRUD()
        extraction_data = {
            "file_id": sample_file.id,
            "tenant_id": sample_file.tenant_id,
            "extraction_type": ExtractionType.TEXT,
            "status": ExtractionStatus.FAILED,
            "error_message": "Processing failed",
            "retry_count": 1,
            "max_retries": 3
        }
        failed_extraction = await crud.create(async_session, extraction_data, mock_redis)
        
        # Retry extraction
        retry_request = RetryExtractionRequest(
            extraction_ids=[failed_extraction.id],
            reset_retry_count=False
        )
        
        retried = await service.retry_extractions(async_session, retry_request, mock_redis)
        
        assert len(retried) == 1
        assert retried[0].status == ExtractionStatus.PENDING
        assert retried[0].retry_count == 2


# Integration Tests
@pytest.mark.integration
class TestExtractionServiceIntegration:
    """Integration tests for Extraction Service components"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_extraction_workflow(self, async_session, sample_tenant, mock_redis, temp_storage):
        """Test complete extraction workflow from file to results"""
        # Create test file with rich content
        file_path = f"{temp_storage}/rich_content.json"
        rich_content = {
            "document": {
                "title": "Test Document",
                "content": "This is a comprehensive test document with various content types.",
                "metadata": {
                    "author": "Test Author",
                    "created_date": "2024-01-01",
                    "tags": ["test", "document", "extraction"]
                },
                "sections": [
                    {"heading": "Introduction", "text": "This is the introduction section."},
                    {"heading": "Content", "text": "This is the main content section."},
                    {"heading": "Conclusion", "text": "This is the conclusion section."}
                ]
            }
        }
        Path(file_path).write_text(json.dumps(rich_content, indent=2))
        
        # Create file record
        file = File(
            tenant_id=sample_tenant.id,
            tenant_code=sample_tenant.code,
            original_filename="rich_content.json",
            stored_filename="stored_rich_content.json",
            file_path=file_path,
            file_size=Path(file_path).stat().st_size,
            mime_type="application/json",
            file_extension=".json",
            file_hash="rich_content_hash"
        )
        async_session.add(file)
        await async_session.commit()
        await async_session.refresh(file)
        
        # Initialize service and request full extraction
        service = ExtractionService()
        
        request = ExtractionRequest(
            file_id=file.id,
            tenant_id=file.tenant_id,
            extraction_type=ExtractionType.FULL,
            config=ExtractionConfig(
                include_metadata=True,
                confidence_threshold=0.8
            )
        )
        
        # Request extraction
        extraction = await service.request_extraction(async_session, request, mock_redis)
        assert extraction.status == ExtractionStatus.PENDING
        
        # Process extraction
        result = await service.process_extraction(async_session, extraction.id, mock_redis)
        
        # Verify results
        assert result.status == ExtractionStatus.COMPLETED
        assert result.extracted_text is not None
        assert "Test Document" in result.extracted_text
        assert "comprehensive test document" in result.extracted_text
        
        # Check metadata
        metadata = json.loads(result.metadata)
        assert "file_stats" in metadata
        assert metadata["file_stats"]["extension"] == ".json"
        
        # Check structured data
        structured_data = json.loads(result.structured_data)
        assert "document" in structured_data
        assert structured_data["document"]["title"] == "Test Document"
        assert len(structured_data["document"]["sections"]) == 3
        
        # Verify confidence and processing metrics
        assert result.confidence_score > 0.8
        assert result.processing_time_ms > 0


# Async Tests
@pytest.mark.async
class TestAsyncExtractionOperations:
    """Test async-specific functionality"""
    
    @pytest.mark.asyncio
    async def test_concurrent_extractions(self, async_session, sample_tenant, mock_redis, temp_storage):
        """Test concurrent extraction processing"""
        service = ExtractionService()
        
        # Create multiple files
        files = []
        for i in range(3):
            file_path = f"{temp_storage}/concurrent_file_{i}.txt"
            Path(file_path).write_text(f"Content for file {i}")
            
            file = File(
                tenant_id=sample_tenant.id,
                tenant_code=sample_tenant.code,
                original_filename=f"concurrent_file_{i}.txt",
                stored_filename=f"stored_concurrent_file_{i}.txt",
                file_path=file_path,
                file_size=20 + i,
                mime_type="text/plain",
                file_extension=".txt",
                file_hash=f"hash_{i}"
            )
            async_session.add(file)
            files.append(file)
        
        await async_session.commit()
        
        # Request extractions for all files
        extraction_requests = []
        for file in files:
            await async_session.refresh(file)
            request = ExtractionRequest(
                file_id=file.id,
                tenant_id=file.tenant_id,
                extraction_type=ExtractionType.TEXT
            )
            extraction = await service.request_extraction(async_session, request, mock_redis)
            extraction_requests.append(extraction)
        
        # Process extractions concurrently
        import asyncio
        tasks = [
            service.process_extraction(async_session, extraction.id, mock_redis)
            for extraction in extraction_requests
        ]
        results = await asyncio.gather(*tasks)
        
        # Verify all completed successfully
        assert len(results) == 3
        assert all(r.status == ExtractionStatus.COMPLETED for r in results)
        assert all(r.extracted_text is not None for r in results)


# Edge Case Tests
@pytest.mark.unit
class TestExtractionEdgeCases:
    """Test edge cases and error handling"""
    
    @pytest.mark.asyncio
    async def test_extraction_with_nonexistent_file(self, async_session, sample_tenant, mock_redis):
        """Test extraction with nonexistent file"""
        service = ExtractionService()
        
        # Create file record pointing to nonexistent file
        file = File(
            tenant_id=sample_tenant.id,
            tenant_code=sample_tenant.code,
            original_filename="nonexistent.txt",
            stored_filename="stored_nonexistent.txt",
            file_path="/nonexistent/path/file.txt",
            file_size=100,
            mime_type="text/plain",
            file_extension=".txt",
            file_hash="nonexistent_hash"
        )
        async_session.add(file)
        await async_session.commit()
        await async_session.refresh(file)
        
        # Request extraction
        request = ExtractionRequest(
            file_id=file.id,
            tenant_id=file.tenant_id,
            extraction_type=ExtractionType.TEXT
        )
        extraction = await service.request_extraction(async_session, request, mock_redis)
        
        # Process extraction (should fail)
        result = await service.process_extraction(async_session, extraction.id, mock_redis)
        
        assert result.status == ExtractionStatus.FAILED
        assert result.error_message is not None
        assert "FileNotFoundError" in result.error_message or "No such file" in result.error_message
    
    @pytest.mark.asyncio
    async def test_extraction_with_corrupted_file(self, async_session, sample_tenant, mock_redis, temp_storage):
        """Test extraction with corrupted/invalid file"""
        service = ExtractionService()
        
        # Create corrupted JSON file
        file_path = f"{temp_storage}/corrupted.json"
        Path(file_path).write_text("{ invalid json content without closing brace")
        
        file = File(
            tenant_id=sample_tenant.id,
            tenant_code=sample_tenant.code,
            original_filename="corrupted.json",
            stored_filename="stored_corrupted.json",
            file_path=file_path,
            file_size=Path(file_path).stat().st_size,
            mime_type="application/json",
            file_extension=".json",
            file_hash="corrupted_hash"
        )
        async_session.add(file)
        await async_session.commit()
        await async_session.refresh(file)
        
        # Request extraction
        request = ExtractionRequest(
            file_id=file.id,
            tenant_id=file.tenant_id,
            extraction_type=ExtractionType.STRUCTURED_DATA
        )
        extraction = await service.request_extraction(async_session, request, mock_redis)
        
        # Process extraction (should handle gracefully)
        result = await service.process_extraction(async_session, extraction.id, mock_redis)
        
        # Should either succeed with partial results or fail gracefully
        assert result.status in [ExtractionStatus.COMPLETED, ExtractionStatus.FAILED]
        if result.status == ExtractionStatus.FAILED:
            assert result.error_message is not None
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, async_session, sample_file, mock_redis):
        """Test extraction that exceeds max retries"""
        crud = ExtractionCRUD()
        
        # Create extraction that has reached max retries
        extraction_data = {
            "file_id": sample_file.id,
            "tenant_id": sample_file.tenant_id,
            "extraction_type": ExtractionType.TEXT,
            "status": ExtractionStatus.FAILED,
            "error_message": "Repeated failures",
            "retry_count": 3,
            "max_retries": 3
        }
        extraction = await crud.create(async_session, extraction_data, mock_redis)
        
        # Try to retry
        service = ExtractionService()
        retry_request = RetryExtractionRequest(
            extraction_ids=[extraction.id],
            reset_retry_count=False
        )
        
        retried = await service.retry_extractions(async_session, retry_request, mock_redis)
        
        # Should not retry extractions that exceeded max retries
        assert len(retried) == 0
    
    @pytest.mark.asyncio
    async def test_confidence_score_calculation(self, async_session, sample_file, mock_redis, temp_storage):
        """Test confidence score calculation edge cases"""
        service = ExtractionService()
        
        # Create file with minimal content
        file_path = f"{temp_storage}/minimal.txt"
        Path(file_path).write_text("x")  # Single character
        
        file = File(
            tenant_id=sample_file.tenant_id,
            tenant_code=sample_file.tenant_code,
            original_filename="minimal.txt",
            stored_filename="stored_minimal.txt",
            file_path=file_path,
            file_size=1,
            mime_type="text/plain",
            file_extension=".txt",
            file_hash="minimal_hash"
        )
        async_session.add(file)
        await async_session.commit()
        await async_session.refresh(file)
        
        # Process extraction
        request = ExtractionRequest(
            file_id=file.id,
            tenant_id=file.tenant_id,
            extraction_type=ExtractionType.TEXT
        )
        extraction = await service.request_extraction(async_session, request, mock_redis)
        result = await service.process_extraction(async_session, extraction.id, mock_redis)
        
        # Confidence should be calculated even for minimal content
        assert result.confidence_score is not None
        assert 0.0 <= result.confidence_score <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
