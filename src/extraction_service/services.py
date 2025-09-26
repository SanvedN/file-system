import asyncio
import json
import time
import traceback
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .crud import ExtractionCRUD
from .models import ExtractionResult
from .schemas import (
    ExtractionRequest, ExtractionResponse, ExtractionUpdate,
    ExtractionSearchRequest, ExtractionListResponse,
    BulkExtractionRequest, BulkExtractionResponse,
    RetryExtractionRequest, ExtractionStats,
    ExtractionStatus, ExtractionType
)
from ..shared.utils import get_file_mime_type
from ..shared.config import settings
from ..shared.cache import redis_client, get_extraction_cache_key
import structlog

logger = structlog.get_logger()


class FileExtractor:
    """Base file extractor class"""
    
    def __init__(self, extraction_type: ExtractionType):
        self.extraction_type = extraction_type
    
    async def extract(self, file_path: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract data from file - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement extract method")
    
    async def validate_result(self, result: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate extraction result"""
        errors = []
        
        # Basic validation
        if not result:
            errors.append("Empty extraction result")
        
        return len(errors) == 0, errors


class TextExtractor(FileExtractor):
    """Text extraction from various file formats"""
    
    def __init__(self):
        super().__init__(ExtractionType.TEXT)
    
    async def extract(self, file_path: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract text content from file"""
        try:
            file_extension = Path(file_path).suffix.lower()
            
            if file_extension == '.txt':
                return await self._extract_from_txt(file_path)
            elif file_extension in ['.pdf']:
                return await self._extract_from_pdf(file_path)
            elif file_extension in ['.doc', '.docx']:
                return await self._extract_from_doc(file_path)
            elif file_extension in ['.json']:
                return await self._extract_from_json(file_path)
            elif file_extension in ['.csv']:
                return await self._extract_from_csv(file_path)
            else:
                # Try to read as plain text
                return await self._extract_from_txt(file_path)
                
        except Exception as e:
            logger.error("Text extraction failed", file_path=file_path, error=str(e))
            raise
    
    async def _extract_from_txt(self, file_path: str) -> Dict[str, Any]:
        """Extract from plain text file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            return {
                "text_content": content,
                "character_count": len(content),
                "line_count": content.count('\n') + 1,
                "word_count": len(content.split()) if content else 0
            }
        except Exception as e:
            raise Exception(f"Failed to extract from text file: {str(e)}")
    
    async def _extract_from_pdf(self, file_path: str) -> Dict[str, Any]:
        """Extract from PDF file (placeholder - would use PyPDF2 or similar)"""
        # In production, use libraries like PyPDF2, pdfplumber, or pymupdf
        return {
            "text_content": "PDF extraction not implemented - placeholder",
            "page_count": 1,
            "extraction_method": "placeholder"
        }
    
    async def _extract_from_doc(self, file_path: str) -> Dict[str, Any]:
        """Extract from Word document (placeholder - would use python-docx)"""
        # In production, use python-docx library
        return {
            "text_content": "DOC extraction not implemented - placeholder",
            "extraction_method": "placeholder"
        }
    
    async def _extract_from_json(self, file_path: str) -> Dict[str, Any]:
        """Extract from JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert JSON to readable text
            text_content = json.dumps(data, indent=2, ensure_ascii=False)
            
            return {
                "text_content": text_content,
                "json_structure": data,
                "key_count": len(data) if isinstance(data, dict) else 0,
                "extraction_method": "json_parsing"
            }
        except Exception as e:
            raise Exception(f"Failed to extract from JSON file: {str(e)}")
    
    async def _extract_from_csv(self, file_path: str) -> Dict[str, Any]:
        """Extract from CSV file"""
        try:
            import csv
            
            rows = []
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                for row in reader:
                    rows.append(row)
            
            # Convert to text representation
            text_content = '\n'.join([','.join(row) for row in rows])
            
            return {
                "text_content": text_content,
                "row_count": len(rows),
                "column_count": len(rows[0]) if rows else 0,
                "headers": rows[0] if rows else [],
                "extraction_method": "csv_parsing"
            }
        except Exception as e:
            raise Exception(f"Failed to extract from CSV file: {str(e)}")


class MetadataExtractor(FileExtractor):
    """Metadata extraction from files"""
    
    def __init__(self):
        super().__init__(ExtractionType.METADATA)
    
    async def extract(self, file_path: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract metadata from file"""
        try:
            import os
            from datetime import datetime
            
            stat = os.stat(file_path)
            file_extension = Path(file_path).suffix.lower()
            mime_type = await get_file_mime_type(file_path)
            
            metadata = {
                "file_name": os.path.basename(file_path),
                "file_size": stat.st_size,
                "file_extension": file_extension,
                "mime_type": mime_type,
                "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "accessed_time": datetime.fromtimestamp(stat.st_atime).isoformat(),
                "permissions": oct(stat.st_mode)[-3:],
            }
            
            # Add format-specific metadata
            if file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
                metadata.update(await self._extract_image_metadata(file_path))
            elif file_extension == '.pdf':
                metadata.update(await self._extract_pdf_metadata(file_path))
            
            return metadata
            
        except Exception as e:
            logger.error("Metadata extraction failed", file_path=file_path, error=str(e))
            raise
    
    async def _extract_image_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract image-specific metadata (placeholder)"""
        # In production, use PIL/Pillow or exifread
        return {
            "image_metadata": "Image metadata extraction not implemented - placeholder"
        }
    
    async def _extract_pdf_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract PDF-specific metadata (placeholder)"""
        # In production, use PyPDF2 or pymupdf
        return {
            "pdf_metadata": "PDF metadata extraction not implemented - placeholder"
        }


class StructuredDataExtractor(FileExtractor):
    """Structured data extraction from files"""
    
    def __init__(self):
        super().__init__(ExtractionType.STRUCTURED_DATA)
    
    async def extract(self, file_path: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract structured data from file"""
        try:
            file_extension = Path(file_path).suffix.lower()
            
            if file_extension == '.json':
                return await self._extract_json_structure(file_path)
            elif file_extension == '.csv':
                return await self._extract_csv_structure(file_path)
            elif file_extension in ['.xml']:
                return await self._extract_xml_structure(file_path)
            else:
                # Try to infer structure from text
                return await self._extract_text_structure(file_path)
                
        except Exception as e:
            logger.error("Structured data extraction failed", file_path=file_path, error=str(e))
            raise
    
    async def _extract_json_structure(self, file_path: str) -> Dict[str, Any]:
        """Extract JSON structure"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return {
                "data_type": "json",
                "structure": data,
                "schema": self._analyze_json_schema(data),
                "total_keys": self._count_json_keys(data)
            }
        except Exception as e:
            raise Exception(f"Failed to extract JSON structure: {str(e)}")
    
    async def _extract_csv_structure(self, file_path: str) -> Dict[str, Any]:
        """Extract CSV structure"""
        try:
            import csv
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if not rows:
                return {"data_type": "csv", "structure": [], "row_count": 0}
            
            headers = rows[0]
            data_rows = rows[1:] if len(rows) > 1 else []
            
            # Analyze column types
            column_analysis = {}
            for i, header in enumerate(headers):
                column_values = [row[i] if i < len(row) else '' for row in data_rows]
                column_analysis[header] = self._analyze_column_type(column_values)
            
            return {
                "data_type": "csv",
                "headers": headers,
                "row_count": len(data_rows),
                "column_count": len(headers),
                "column_analysis": column_analysis,
                "sample_rows": data_rows[:5] if data_rows else []
            }
        except Exception as e:
            raise Exception(f"Failed to extract CSV structure: {str(e)}")
    
    async def _extract_xml_structure(self, file_path: str) -> Dict[str, Any]:
        """Extract XML structure (placeholder)"""
        # In production, use xml.etree.ElementTree or lxml
        return {
            "data_type": "xml",
            "structure": "XML extraction not implemented - placeholder"
        }
    
    async def _extract_text_structure(self, file_path: str) -> Dict[str, Any]:
        """Extract structure from plain text"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            lines = content.split('\n')
            
            # Basic structure analysis
            structure = {
                "data_type": "text",
                "line_count": len(lines),
                "empty_lines": sum(1 for line in lines if not line.strip()),
                "max_line_length": max(len(line) for line in lines) if lines else 0,
                "avg_line_length": sum(len(line) for line in lines) / len(lines) if lines else 0
            }
            
            # Try to detect patterns
            if any(',' in line for line in lines[:10]):
                structure["possible_csv"] = True
            if any(line.strip().startswith('{') for line in lines):
                structure["possible_json"] = True
                
            return structure
            
        except Exception as e:
            raise Exception(f"Failed to extract text structure: {str(e)}")
    
    def _analyze_json_schema(self, data: Any) -> Dict[str, Any]:
        """Analyze JSON schema"""
        if isinstance(data, dict):
            return {
                "type": "object",
                "properties": {k: self._analyze_json_schema(v) for k, v in data.items()}
            }
        elif isinstance(data, list):
            if data:
                return {
                    "type": "array",
                    "items": self._analyze_json_schema(data[0])
                }
            else:
                return {"type": "array", "items": {}}
        else:
            return {"type": type(data).__name__}
    
    def _count_json_keys(self, data: Any) -> int:
        """Count total keys in JSON structure"""
        if isinstance(data, dict):
            return len(data) + sum(self._count_json_keys(v) for v in data.values())
        elif isinstance(data, list):
            return sum(self._count_json_keys(item) for item in data)
        else:
            return 0
    
    def _analyze_column_type(self, values: List[str]) -> Dict[str, Any]:
        """Analyze column data type"""
        non_empty_values = [v for v in values if v.strip()]
        
        if not non_empty_values:
            return {"type": "empty", "sample_values": []}
        
        # Try to detect numeric
        try:
            numeric_values = [float(v) for v in non_empty_values[:10]]
            return {
                "type": "numeric",
                "sample_values": non_empty_values[:5],
                "min": min(numeric_values),
                "max": max(numeric_values)
            }
        except ValueError:
            pass
        
        # Check for date patterns
        date_patterns = ['/', '-', ':', 'T']
        if any(pattern in non_empty_values[0] for pattern in date_patterns):
            return {"type": "possible_date", "sample_values": non_empty_values[:5]}
        
        return {"type": "text", "sample_values": non_empty_values[:5]}


class ExtractionService:
    """Main extraction service orchestrator"""
    
    def __init__(self):
        self.extractors = {
            ExtractionType.TEXT: TextExtractor(),
            ExtractionType.METADATA: MetadataExtractor(),
            ExtractionType.STRUCTURED_DATA: StructuredDataExtractor(),
        }
    
    async def request_extraction(
        self,
        db: AsyncSession,
        request: ExtractionRequest
    ) -> ExtractionResponse:
        """Request a new extraction"""
        try:
            # Verify file exists (would check file service)
            # For now, assume file_id is valid
            
            # Create extraction record
            extraction_data = {
                "file_id": request.file_id,
                "tenant_id": "placeholder",  # Would get from file record
                "extraction_type": request.extraction_type,
                "status": ExtractionStatus.PENDING,
                "max_retries": request.max_retries,
                "extraction_config": json.dumps(request.extraction_config) if request.extraction_config else None
            }
            
            extraction = await ExtractionCRUD.create(db, extraction_data)
            
            # Convert to response
            return ExtractionResponse(
                id=extraction.id,
                file_id=extraction.file_id,
                tenant_id=extraction.tenant_id,
                extraction_type=extraction.extraction_type,
                extractor_version=extraction.extractor_version,
                status=extraction.status,
                progress_percentage=extraction.progress_percentage,
                created_at=extraction.created_at,
                last_updated=extraction.last_updated,
                max_retries=extraction.max_retries,
                validation_passed=extraction.validation_passed
            )
            
        except Exception as e:
            logger.error("Failed to request extraction", error=str(e))
            raise HTTPException(status_code=500, detail="Failed to request extraction")
    
    async def process_extraction(
        self,
        db: AsyncSession,
        extraction_id: str,
        file_path: str
    ) -> bool:
        """Process a single extraction"""
        try:
            # Get extraction record
            extraction = await ExtractionCRUD.get_by_id(db, extraction_id)
            if not extraction:
                logger.error("Extraction not found", extraction_id=extraction_id)
                return False
            
            if extraction.status != ExtractionStatus.PENDING:
                logger.warning("Extraction not in pending status", extraction_id=extraction_id, status=extraction.status)
                return False
            
            # Update status to processing
            await ExtractionCRUD.update(db, extraction_id, ExtractionUpdate(
                status=ExtractionStatus.PROCESSING,
                progress_percentage=0
            ))
            
            start_time = time.time()
            
            try:
                # Get appropriate extractor
                extractor = self.extractors.get(extraction.extraction_type)
                if not extractor:
                    raise Exception(f"No extractor available for type: {extraction.extraction_type}")
                
                # Parse config
                config = {}
                if extraction.extraction_config:
                    config = json.loads(extraction.extraction_config)
                
                # Update progress
                await ExtractionCRUD.update(db, extraction_id, ExtractionUpdate(
                    progress_percentage=25
                ))
                
                # Perform extraction
                logger.info("Starting extraction", extraction_id=extraction_id, type=extraction.extraction_type)
                
                if extraction.extraction_type == ExtractionType.FULL:
                    # For FULL extraction, run all extractors
                    result = await self._process_full_extraction(file_path, config)
                else:
                    # Single extractor
                    result = await extractor.extract(file_path, config)
                
                # Update progress
                await ExtractionCRUD.update(db, extraction_id, ExtractionUpdate(
                    progress_percentage=75
                ))
                
                # Validate result
                is_valid, validation_errors = await extractor.validate_result(result)
                
                # Calculate metrics
                processing_time = int((time.time() - start_time) * 1000)
                confidence_score = self._calculate_confidence_score(result, extraction.extraction_type)
                
                # Update with results
                update_data = ExtractionUpdate(
                    status=ExtractionStatus.COMPLETED,
                    progress_percentage=100,
                    processing_time_ms=processing_time,
                    confidence_score=confidence_score,
                    validation_passed=is_valid
                )
                
                # Set extraction results based on type
                if extraction.extraction_type == ExtractionType.TEXT:
                    update_data.extracted_text = result.get("text_content")
                elif extraction.extraction_type == ExtractionType.METADATA:
                    update_data.metadata = result
                elif extraction.extraction_type == ExtractionType.STRUCTURED_DATA:
                    update_data.structured_data = result
                elif extraction.extraction_type == ExtractionType.FULL:
                    update_data.extracted_text = result.get("text", {}).get("text_content")
                    update_data.structured_data = result.get("structured_data")
                    update_data.metadata = result.get("metadata")
                    update_data.file_analysis = result.get("analysis")
                
                await ExtractionCRUD.update(db, extraction_id, update_data)
                
                logger.info(
                    "Extraction completed successfully",
                    extraction_id=extraction_id,
                    processing_time_ms=processing_time,
                    confidence_score=confidence_score
                )
                
                return True
                
            except Exception as e:
                # Handle extraction failure
                error_message = str(e)
                logger.error("Extraction failed", extraction_id=extraction_id, error=error_message)
                
                await ExtractionCRUD.update(db, extraction_id, ExtractionUpdate(
                    status=ExtractionStatus.FAILED,
                    error_message=error_message,
                    error_code="EXTRACTION_ERROR",
                    processing_time_ms=int((time.time() - start_time) * 1000)
                ))
                
                return False
                
        except Exception as e:
            logger.error("Failed to process extraction", extraction_id=extraction_id, error=str(e))
            return False
    
    async def _process_full_extraction(self, file_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Process full extraction using all extractors"""
        results = {}
        
        try:
            # Run all extractors
            text_extractor = self.extractors[ExtractionType.TEXT]
            metadata_extractor = self.extractors[ExtractionType.METADATA]
            structured_extractor = self.extractors[ExtractionType.STRUCTURED_DATA]
            
            # Extract text
            try:
                results["text"] = await text_extractor.extract(file_path, config)
            except Exception as e:
                results["text"] = {"error": str(e)}
            
            # Extract metadata
            try:
                results["metadata"] = await metadata_extractor.extract(file_path, config)
            except Exception as e:
                results["metadata"] = {"error": str(e)}
            
            # Extract structured data
            try:
                results["structured_data"] = await structured_extractor.extract(file_path, config)
            except Exception as e:
                results["structured_data"] = {"error": str(e)}
            
            # Generate analysis summary
            results["analysis"] = {
                "extraction_timestamp": datetime.utcnow().isoformat(),
                "extractors_used": ["text", "metadata", "structured_data"],
                "success_count": len([r for r in results.values() if not isinstance(r, dict) or "error" not in r]),
                "total_extractors": 3
            }
            
            return results
            
        except Exception as e:
            raise Exception(f"Full extraction failed: {str(e)}")
    
    def _calculate_confidence_score(self, result: Dict[str, Any], extraction_type: ExtractionType) -> float:
        """Calculate confidence score for extraction result"""
        try:
            if not result:
                return 0.0
            
            if extraction_type == ExtractionType.TEXT:
                text_content = result.get("text_content", "")
                if not text_content:
                    return 0.0
                # Score based on content length and structure
                base_score = min(0.8, len(text_content) / 1000)
                return base_score + 0.2  # Base confidence
            
            elif extraction_type == ExtractionType.METADATA:
                # Score based on number of metadata fields
                field_count = len(result)
                return min(1.0, field_count / 10)
            
            elif extraction_type == ExtractionType.STRUCTURED_DATA:
                # Score based on structure complexity
                if "structure" in result:
                    return 0.9 if result["structure"] else 0.3
                return 0.5
            
            elif extraction_type == ExtractionType.FULL:
                # Average of all sub-extractions
                scores = []
                if "text" in result and "error" not in result["text"]:
                    scores.append(0.8)
                if "metadata" in result and "error" not in result["metadata"]:
                    scores.append(0.8)
                if "structured_data" in result and "error" not in result["structured_data"]:
                    scores.append(0.8)
                
                return sum(scores) / len(scores) if scores else 0.0
            
            return 0.5  # Default confidence
            
        except Exception:
            return 0.0
    
    async def get_extraction(self, db: AsyncSession, extraction_id: str) -> Optional[ExtractionResponse]:
        """Get extraction by ID"""
        extraction = await ExtractionCRUD.get_by_id(db, extraction_id)
        if not extraction:
            return None
        
        # Parse JSON fields
        structured_data = None
        metadata = None
        file_analysis = None
        extraction_quality = None
        
        if extraction.structured_data:
            try:
                structured_data = json.loads(extraction.structured_data)
            except json.JSONDecodeError:
                pass
        
        if extraction.metadata:
            try:
                metadata = json.loads(extraction.metadata)
            except json.JSONDecodeError:
                pass
        
        if extraction.file_analysis:
            try:
                file_analysis = json.loads(extraction.file_analysis)
            except json.JSONDecodeError:
                pass
        
        if extraction.extraction_quality:
            try:
                extraction_quality = json.loads(extraction.extraction_quality)
            except json.JSONDecodeError:
                pass
        
        return ExtractionResponse(
            id=extraction.id,
            file_id=extraction.file_id,
            tenant_id=extraction.tenant_id,
            extraction_type=extraction.extraction_type,
            extractor_version=extraction.extractor_version,
            status=extraction.status,
            progress_percentage=extraction.progress_percentage,
            extracted_text=extraction.extracted_text,
            structured_data=structured_data,
            metadata=metadata,
            file_analysis=file_analysis,
            confidence_score=extraction.confidence_score,
            processing_time_ms=extraction.processing_time_ms,
            memory_usage_mb=extraction.memory_usage_mb,
            error_message=extraction.error_message,
            error_code=extraction.error_code,
            retry_count=extraction.retry_count,
            max_retries=extraction.max_retries,
            created_at=extraction.created_at,
            started_at=extraction.started_at,
            completed_at=extraction.completed_at,
            last_updated=extraction.last_updated,
            extraction_quality=extraction_quality,
            validation_passed=extraction.validation_passed
        )
    
    async def search_extractions(
        self,
        db: AsyncSession,
        search_params: ExtractionSearchRequest
    ) -> ExtractionListResponse:
        """Search extractions with advanced filtering"""
        extractions, total_count = await ExtractionCRUD.search_extractions(db, search_params)
        
        extraction_summaries = []
        for extraction in extractions:
            extraction_summaries.append({
                "id": extraction.id,
                "file_id": extraction.file_id,
                "extraction_type": extraction.extraction_type,
                "status": extraction.status,
                "progress_percentage": extraction.progress_percentage,
                "confidence_score": extraction.confidence_score,
                "created_at": extraction.created_at,
                "completed_at": extraction.completed_at,
                "processing_time_ms": extraction.processing_time_ms,
                "validation_passed": extraction.validation_passed
            })
        
        return ExtractionListResponse(
            extractions=extraction_summaries,
            total_count=total_count,
            page=search_params.page,
            limit=search_params.limit,
            has_next=((search_params.page - 1) * search_params.limit + search_params.limit) < total_count,
            has_previous=search_params.page > 1
        )
    
    async def bulk_request_extractions(
        self,
        db: AsyncSession,
        request: BulkExtractionRequest
    ) -> BulkExtractionResponse:
        """Request multiple extractions"""
        created_extractions = []
        failed_requests = []
        
        for file_id in request.file_ids:
            try:
                extraction_request = ExtractionRequest(
                    file_id=file_id,
                    extraction_type=request.extraction_type,
                    extraction_config=request.extraction_config,
                    priority=request.priority,
                    max_retries=request.max_retries
                )
                
                extraction = await self.request_extraction(db, extraction_request)
                created_extractions.append(extraction.id)
                
            except Exception as e:
                failed_requests.append({"file_id": file_id, "error": str(e)})
        
        return BulkExtractionResponse(
            created_extractions=created_extractions,
            failed_requests=failed_requests,
            total_created=len(created_extractions),
            total_failed=len(failed_requests)
        )
    
    async def retry_extractions(
        self,
        db: AsyncSession,
        request: RetryExtractionRequest
    ) -> Dict[str, Any]:
        """Retry failed extractions"""
        retried = []
        failed = []
        
        for extraction_id in request.extraction_ids:
            try:
                extraction = await ExtractionCRUD.get_by_id(db, extraction_id)
                if not extraction:
                    failed.append({"extraction_id": extraction_id, "error": "Extraction not found"})
                    continue
                
                if not extraction.can_retry and not request.force_retry:
                    failed.append({"extraction_id": extraction_id, "error": "Max retries exceeded"})
                    continue
                
                # Reset extraction for retry
                await ExtractionCRUD.update(db, extraction_id, ExtractionUpdate(
                    status=ExtractionStatus.PENDING,
                    progress_percentage=0,
                    error_message=None,
                    error_code=None
                ))
                
                # Increment retry count
                await ExtractionCRUD.increment_retry_count(db, extraction_id)
                
                retried.append(extraction_id)
                
            except Exception as e:
                failed.append({"extraction_id": extraction_id, "error": str(e)})
        
        return {
            "retried_extractions": retried,
            "failed_retries": failed,
            "total_retried": len(retried),
            "total_failed": len(failed)
        }
    
    async def get_extraction_stats(
        self,
        db: AsyncSession,
        tenant_id: Optional[str] = None
    ) -> ExtractionStats:
        """Get extraction statistics"""
        stats_data = await ExtractionCRUD.get_extraction_stats(db, tenant_id)
        return ExtractionStats(**stats_data)
