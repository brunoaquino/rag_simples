"""
Sistema de Validação para Ingestão de Documentos
Módulo responsável por validar a integridade e qualidade dos documentos processados.
"""

import logging
import re
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import hashlib
import mimetypes

from .chunking_system import Chunk, ChunkConfig
from .metadata_extractor import MetadataExtractor
from .document_versioning import DocumentVersion, ProcessingResult

logger = logging.getLogger(__name__)

class ValidationLevel(Enum):
    """Níveis de validação."""
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"
    CUSTOM = "custom"

class ValidationSeverity(Enum):
    """Severidade dos resultados de validação."""
    INFO = "info"
    WARNING = "warning"  
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class ValidationRule:
    """Representa uma regra de validação."""
    name: str
    description: str
    severity: ValidationSeverity
    enabled: bool = True
    custom_params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ValidationIssue:
    """Representa um problema encontrado na validação."""
    rule_name: str
    severity: ValidationSeverity
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    location: Optional[str] = None
    suggested_fix: Optional[str] = None

@dataclass
class ValidationResult:
    """Resultado de uma validação."""
    is_valid: bool
    issues: List[ValidationIssue]
    score: float  # 0.0 a 1.0
    validation_level: ValidationLevel
    total_checks: int
    passed_checks: int
    failed_checks: int
    warnings: int
    errors: int
    processing_time: float

    def has_critical_issues(self) -> bool:
        """Verifica se há problemas críticos."""
        return any(issue.severity == ValidationSeverity.CRITICAL for issue in self.issues)
    
    def has_errors(self) -> bool:
        """Verifica se há erros."""
        return any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)
    
    def get_issues_by_severity(self, severity: ValidationSeverity) -> List[ValidationIssue]:
        """Retorna problemas de uma severidade específica."""
        return [issue for issue in self.issues if issue.severity == severity]

class DocumentValidator:
    """Validador para documentos brutos."""
    
    def __init__(self):
        """Inicializa o validador de documentos."""
        self.rules = self._initialize_document_rules()
    
    def _initialize_document_rules(self) -> Dict[str, ValidationRule]:
        """Inicializa as regras de validação de documentos."""
        return {
            'file_exists': ValidationRule(
                name='file_exists',
                description='Verifica se o arquivo existe no sistema de arquivos',
                severity=ValidationSeverity.CRITICAL
            ),
            'file_accessible': ValidationRule(
                name='file_accessible',
                description='Verifica se o arquivo pode ser lido',
                severity=ValidationSeverity.CRITICAL
            ),
            'file_size': ValidationRule(
                name='file_size',
                description='Valida o tamanho do arquivo',
                severity=ValidationSeverity.WARNING,
                custom_params={'min_size': 1, 'max_size': 100 * 1024 * 1024}  # 100MB
            ),
            'file_type': ValidationRule(
                name='file_type',
                description='Valida o tipo MIME do arquivo',
                severity=ValidationSeverity.ERROR,
                custom_params={'allowed_types': [
                    'text/plain', 'text/markdown', 'application/pdf',
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                ]}
            ),
            'file_extension': ValidationRule(
                name='file_extension',
                description='Valida a extensão do arquivo',
                severity=ValidationSeverity.WARNING,
                custom_params={'allowed_extensions': ['.txt', '.md', '.pdf', '.docx']}
            ),
            'filename_format': ValidationRule(
                name='filename_format',
                description='Valida o formato do nome do arquivo',
                severity=ValidationSeverity.INFO,
                custom_params={'pattern': r'^[a-zA-Z0-9_\-\.\s]+$'}
            ),
            'encoding_detection': ValidationRule(
                name='encoding_detection',
                description='Verifica se o encoding do arquivo pode ser detectado',
                severity=ValidationSeverity.ERROR
            )
        }
    
    def validate_file(self, file_path: Union[str, Path]) -> ValidationResult:
        """Valida um arquivo de documento."""
        start_time = time.time()
        
        file_path = Path(file_path)
        issues = []
        total_checks = len(self.rules)
        passed_checks = 0
        
        # Verifica se arquivo existe
        if self.rules['file_exists'].enabled:
            if not file_path.exists():
                issues.append(ValidationIssue(
                    rule_name='file_exists',
                    severity=ValidationSeverity.CRITICAL,
                    message=f'Arquivo não encontrado: {file_path}',
                    details={'file_path': str(file_path)}
                ))
            else:
                passed_checks += 1
        
        # Se arquivo não existe, não podemos fazer outras validações
        if not file_path.exists():
            processing_time = time.time() - start_time
            return ValidationResult(
                is_valid=False,
                issues=issues,
                score=0.0,
                validation_level=ValidationLevel.BASIC,
                total_checks=total_checks,
                passed_checks=passed_checks,
                failed_checks=total_checks - passed_checks,
                warnings=len([i for i in issues if i.severity == ValidationSeverity.WARNING]),
                errors=len([i for i in issues if i.severity == ValidationSeverity.ERROR]),
                processing_time=processing_time
            )
        
        # Verifica se arquivo é acessível
        if self.rules['file_accessible'].enabled:
            try:
                with open(file_path, 'rb') as f:
                    f.read(1)  # Tenta ler 1 byte
                passed_checks += 1
            except PermissionError:
                issues.append(ValidationIssue(
                    rule_name='file_accessible',
                    severity=ValidationSeverity.CRITICAL,
                    message=f'Sem permissão para ler o arquivo: {file_path}',
                    details={'file_path': str(file_path)},
                    suggested_fix='Verifique as permissões do arquivo'
                ))
            except Exception as e:
                issues.append(ValidationIssue(
                    rule_name='file_accessible',
                    severity=ValidationSeverity.ERROR,
                    message=f'Erro ao acessar arquivo: {str(e)}',
                    details={'file_path': str(file_path), 'error': str(e)}
                ))
        
        # Valida tamanho do arquivo
        if self.rules['file_size'].enabled:
            file_size = file_path.stat().st_size
            min_size = self.rules['file_size'].custom_params['min_size']
            max_size = self.rules['file_size'].custom_params['max_size']
            
            if file_size < min_size:
                issues.append(ValidationIssue(
                    rule_name='file_size',
                    severity=ValidationSeverity.WARNING,
                    message=f'Arquivo muito pequeno: {file_size} bytes (mínimo: {min_size})',
                    details={'file_size': file_size, 'min_size': min_size}
                ))
            elif file_size > max_size:
                issues.append(ValidationIssue(
                    rule_name='file_size',
                    severity=ValidationSeverity.WARNING,
                    message=f'Arquivo muito grande: {file_size} bytes (máximo: {max_size})',
                    details={'file_size': file_size, 'max_size': max_size},
                    suggested_fix='Considere dividir o arquivo em partes menores'
                ))
            else:
                passed_checks += 1
        
        # Valida tipo MIME
        if self.rules['file_type'].enabled:
            mime_type, _ = mimetypes.guess_type(file_path)
            allowed_types = self.rules['file_type'].custom_params['allowed_types']
            
            if mime_type not in allowed_types:
                issues.append(ValidationIssue(
                    rule_name='file_type',
                    severity=ValidationSeverity.ERROR,
                    message=f'Tipo de arquivo não suportado: {mime_type}',
                    details={'detected_type': mime_type, 'allowed_types': allowed_types},
                    suggested_fix=f'Use um dos tipos suportados: {", ".join(allowed_types)}'
                ))
            else:
                passed_checks += 1
        
        # Valida extensão
        if self.rules['file_extension'].enabled:
            extension = file_path.suffix.lower()
            allowed_extensions = self.rules['file_extension'].custom_params['allowed_extensions']
            
            if extension not in allowed_extensions:
                issues.append(ValidationIssue(
                    rule_name='file_extension',
                    severity=ValidationSeverity.WARNING,
                    message=f'Extensão não recomendada: {extension}',
                    details={'detected_extension': extension, 'allowed_extensions': allowed_extensions}
                ))
            else:
                passed_checks += 1
        
        # Valida formato do nome do arquivo
        if self.rules['filename_format'].enabled:
            pattern = self.rules['filename_format'].custom_params['pattern']
            if not re.match(pattern, file_path.name):
                issues.append(ValidationIssue(
                    rule_name='filename_format',
                    severity=ValidationSeverity.INFO,
                    message=f'Nome do arquivo não segue padrão recomendado: {file_path.name}',
                    details={'filename': file_path.name, 'pattern': pattern},
                    suggested_fix='Use apenas letras, números, hífens, sublinhados e pontos'
                ))
            else:
                passed_checks += 1
        
        # Valida encoding (para arquivos de texto)
        if self.rules['encoding_detection'].enabled and mime_type and mime_type.startswith('text/'):
            try:
                import chardet
                with open(file_path, 'rb') as f:
                    raw_data = f.read(10000)  # Lê primeiros 10KB
                detected = chardet.detect(raw_data)
                
                if detected['confidence'] < 0.7:
                    issues.append(ValidationIssue(
                        rule_name='encoding_detection',
                        severity=ValidationSeverity.WARNING,
                        message=f'Encoding do arquivo não detectado com confiança: {detected}',
                        details={'detected_encoding': detected},
                        suggested_fix='Considere salvar o arquivo em UTF-8'
                    ))
                else:
                    passed_checks += 1
            except ImportError:
                logger.warning("chardet não instalado, pulando detecção de encoding")
                passed_checks += 1  # Não conta como falha
            except Exception as e:
                issues.append(ValidationIssue(
                    rule_name='encoding_detection',
                    severity=ValidationSeverity.ERROR,
                    message=f'Erro ao detectar encoding: {str(e)}',
                    details={'error': str(e)}
                ))
        
        # Calcula score e resultado
        failed_checks = total_checks - passed_checks
        score = passed_checks / total_checks if total_checks > 0 else 0.0
        
        # Determina se é válido (sem problemas críticos ou erros)
        has_critical = any(issue.severity == ValidationSeverity.CRITICAL for issue in issues)
        has_errors = any(issue.severity == ValidationSeverity.ERROR for issue in issues)
        is_valid = not (has_critical or has_errors)
        
        processing_time = time.time() - start_time
        
        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            score=score,
            validation_level=ValidationLevel.STANDARD,
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            warnings=len([i for i in issues if i.severity == ValidationSeverity.WARNING]),
            errors=len([i for i in issues if i.severity == ValidationSeverity.ERROR]),
            processing_time=processing_time
        )

class ContentValidator:
    """Validador para conteúdo extraído de documentos."""
    
    def __init__(self):
        """Inicializa o validador de conteúdo."""
        self.rules = self._initialize_content_rules()
    
    def _initialize_content_rules(self) -> Dict[str, ValidationRule]:
        """Inicializa as regras de validação de conteúdo."""
        return {
            'content_not_empty': ValidationRule(
                name='content_not_empty',
                description='Verifica se o conteúdo não está vazio',
                severity=ValidationSeverity.CRITICAL
            ),
            'content_length': ValidationRule(
                name='content_length',
                description='Valida o comprimento do conteúdo',
                severity=ValidationSeverity.WARNING,
                custom_params={'min_length': 10, 'max_length': 10000000}
            ),
            'text_quality': ValidationRule(
                name='text_quality',
                description='Avalia a qualidade do texto extraído',
                severity=ValidationSeverity.WARNING,
                custom_params={'min_word_ratio': 0.7, 'max_special_chars_ratio': 0.3}
            ),
            'language_detection': ValidationRule(
                name='language_detection',
                description='Detecta o idioma do conteúdo',
                severity=ValidationSeverity.INFO
            ),
            'encoding_consistency': ValidationRule(
                name='encoding_consistency',
                description='Verifica consistência de encoding',
                severity=ValidationSeverity.ERROR
            ),
            'structure_integrity': ValidationRule(
                name='structure_integrity',
                description='Verifica integridade da estrutura do documento',
                severity=ValidationSeverity.WARNING
            )
        }
    
    def validate_content(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Valida conteúdo extraído de documento."""
        start_time = time.time()
        
        issues = []
        total_checks = len(self.rules)
        passed_checks = 0
        
        # Verifica se conteúdo não está vazio
        if self.rules['content_not_empty'].enabled:
            if not content or not content.strip():
                issues.append(ValidationIssue(
                    rule_name='content_not_empty',
                    severity=ValidationSeverity.CRITICAL,
                    message='Conteúdo vazio ou apenas espaços em branco',
                    details={'content_length': len(content) if content else 0}
                ))
            else:
                passed_checks += 1
        
        # Se não há conteúdo, não podemos fazer outras validações
        if not content or not content.strip():
            processing_time = time.time() - start_time
            return ValidationResult(
                is_valid=False,
                issues=issues,
                score=0.0,
                validation_level=ValidationLevel.BASIC,
                total_checks=total_checks,
                passed_checks=passed_checks,
                failed_checks=total_checks - passed_checks,
                warnings=0,
                errors=0,
                processing_time=processing_time
            )
        
        content = content.strip()
        
        # Valida comprimento do conteúdo
        if self.rules['content_length'].enabled:
            min_length = self.rules['content_length'].custom_params['min_length']
            max_length = self.rules['content_length'].custom_params['max_length']
            
            if len(content) < min_length:
                issues.append(ValidationIssue(
                    rule_name='content_length',
                    severity=ValidationSeverity.WARNING,
                    message=f'Conteúdo muito curto: {len(content)} caracteres (mínimo: {min_length})',
                    details={'content_length': len(content), 'min_length': min_length}
                ))
            elif len(content) > max_length:
                issues.append(ValidationIssue(
                    rule_name='content_length',
                    severity=ValidationSeverity.WARNING,
                    message=f'Conteúdo muito longo: {len(content)} caracteres (máximo: {max_length})',
                    details={'content_length': len(content), 'max_length': max_length}
                ))
            else:
                passed_checks += 1
        
        # Avalia qualidade do texto
        if self.rules['text_quality'].enabled:
            words = re.findall(r'\b\w+\b', content)
            total_chars = len(content)
            word_chars = sum(len(word) for word in words)
            word_ratio = word_chars / total_chars if total_chars > 0 else 0
            
            special_chars = len(re.findall(r'[^\w\s.,!?;:\-\(\)\[\]{}"\']', content))
            special_chars_ratio = special_chars / total_chars if total_chars > 0 else 0
            
            min_word_ratio = self.rules['text_quality'].custom_params['min_word_ratio']
            max_special_chars_ratio = self.rules['text_quality'].custom_params['max_special_chars_ratio']
            
            if word_ratio < min_word_ratio:
                issues.append(ValidationIssue(
                    rule_name='text_quality',
                    severity=ValidationSeverity.WARNING,
                    message=f'Baixa proporção de palavras: {word_ratio:.2%} (mínimo: {min_word_ratio:.2%})',
                    details={'word_ratio': word_ratio, 'min_word_ratio': min_word_ratio},
                    suggested_fix='Verifique se o documento foi extraído corretamente'
                ))
            elif special_chars_ratio > max_special_chars_ratio:
                issues.append(ValidationIssue(
                    rule_name='text_quality',
                    severity=ValidationSeverity.WARNING,
                    message=f'Muitos caracteres especiais: {special_chars_ratio:.2%} (máximo: {max_special_chars_ratio:.2%})',
                    details={'special_chars_ratio': special_chars_ratio, 'max_special_chars_ratio': max_special_chars_ratio}
                ))
            else:
                passed_checks += 1
        
        # Detecta idioma
        if self.rules['language_detection'].enabled:
            try:
                import langdetect
                detected_lang = langdetect.detect(content)
                
                # Info apenas, não conta como erro
                issues.append(ValidationIssue(
                    rule_name='language_detection',
                    severity=ValidationSeverity.INFO,
                    message=f'Idioma detectado: {detected_lang}',
                    details={'detected_language': detected_lang}
                ))
                passed_checks += 1
            except ImportError:
                logger.info("langdetect não instalado, pulando detecção de idioma")
                passed_checks += 1
            except Exception as e:
                issues.append(ValidationIssue(
                    rule_name='language_detection',
                    severity=ValidationSeverity.INFO,
                    message=f'Não foi possível detectar idioma: {str(e)}',
                    details={'error': str(e)}
                ))
                passed_checks += 1  # Não é crítico
        
        # Verifica consistência de encoding
        if self.rules['encoding_consistency'].enabled:
            try:
                # Tenta codificar/decodificar o conteúdo
                content.encode('utf-8').decode('utf-8')
                passed_checks += 1
            except UnicodeError as e:
                issues.append(ValidationIssue(
                    rule_name='encoding_consistency',
                    severity=ValidationSeverity.ERROR,
                    message=f'Problemas de encoding no conteúdo: {str(e)}',
                    details={'error': str(e)},
                    suggested_fix='Verifique o encoding do arquivo original'
                ))
        
        # Verifica integridade da estrutura
        if self.rules['structure_integrity'].enabled:
            # Análises básicas de estrutura
            lines = content.split('\n')
            empty_lines = sum(1 for line in lines if not line.strip())
            empty_ratio = empty_lines / len(lines) if lines else 0
            
            # Se mais de 70% das linhas estão vazias, pode indicar problema
            if empty_ratio > 0.7:
                issues.append(ValidationIssue(
                    rule_name='structure_integrity',
                    severity=ValidationSeverity.WARNING,
                    message=f'Muitas linhas vazias: {empty_ratio:.2%} do conteúdo',
                    details={'empty_lines_ratio': empty_ratio},
                    suggested_fix='Verifique se o documento foi extraído corretamente'
                ))
            else:
                passed_checks += 1
        
        # Calcula score e resultado
        failed_checks = total_checks - passed_checks
        score = passed_checks / total_checks if total_checks > 0 else 0.0
        
        # Determina se é válido
        has_critical = any(issue.severity == ValidationSeverity.CRITICAL for issue in issues)
        has_errors = any(issue.severity == ValidationSeverity.ERROR for issue in issues)
        is_valid = not (has_critical or has_errors)
        
        processing_time = time.time() - start_time
        
        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            score=score,
            validation_level=ValidationLevel.STANDARD,
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            warnings=len([i for i in issues if i.severity == ValidationSeverity.WARNING]),
            errors=len([i for i in issues if i.severity == ValidationSeverity.ERROR]),
            processing_time=processing_time
        )

class ChunkValidator:
    """Validador para chunks gerados."""
    
    def __init__(self, chunk_config: Optional[ChunkConfig] = None):
        """Inicializa o validador de chunks."""
        self.chunk_config = chunk_config or ChunkConfig()
        self.rules = self._initialize_chunk_rules()
    
    def _initialize_chunk_rules(self) -> Dict[str, ValidationRule]:
        """Inicializa as regras de validação de chunks."""
        return {
            'chunk_not_empty': ValidationRule(
                name='chunk_not_empty',
                description='Verifica se o chunk não está vazio',
                severity=ValidationSeverity.CRITICAL
            ),
            'chunk_size_limits': ValidationRule(
                name='chunk_size_limits',
                description='Valida limites de tamanho do chunk',
                severity=ValidationSeverity.WARNING
            ),
            'overlap_validation': ValidationRule(
                name='overlap_validation',
                description='Valida sobreposição entre chunks',
                severity=ValidationSeverity.WARNING
            ),
            'chunk_boundaries': ValidationRule(
                name='chunk_boundaries',
                description='Verifica se os limites dos chunks são apropriados',
                severity=ValidationSeverity.INFO
            ),
            'content_coherence': ValidationRule(
                name='content_coherence',
                description='Avalia coerência do conteúdo do chunk',
                severity=ValidationSeverity.WARNING
            ),
            'metadata_consistency': ValidationRule(
                name='metadata_consistency',
                description='Verifica consistência dos metadados do chunk',
                severity=ValidationSeverity.ERROR
            )
        }
    
    def validate_chunks(self, chunks: List[Chunk], original_content: str = "") -> ValidationResult:
        """Valida uma lista de chunks."""
        start_time = time.time()
        
        issues = []
        total_checks = len(self.rules) * len(chunks) if chunks else len(self.rules)
        passed_checks = 0
        
        if not chunks:
            issues.append(ValidationIssue(
                rule_name='chunk_not_empty',
                severity=ValidationSeverity.CRITICAL,
                message='Nenhum chunk foi gerado',
                details={'chunks_count': 0}
            ))
            
            processing_time = time.time() - start_time
            return ValidationResult(
                is_valid=False,
                issues=issues,
                score=0.0,
                validation_level=ValidationLevel.BASIC,
                total_checks=total_checks,
                passed_checks=0,
                failed_checks=total_checks,
                warnings=0,
                errors=0,
                processing_time=processing_time
            )
        
        # Valida cada chunk individualmente
        for i, chunk in enumerate(chunks):
            
            # Verifica se chunk não está vazio
            if self.rules['chunk_not_empty'].enabled:
                if not chunk.text or not chunk.text.strip():
                    issues.append(ValidationIssue(
                        rule_name='chunk_not_empty',
                        severity=ValidationSeverity.CRITICAL,
                        message=f'Chunk {i} está vazio',
                        details={'chunk_index': i, 'chunk_id': chunk.chunk_id},
                        location=f'Chunk {i}'
                    ))
                else:
                    passed_checks += 1
            
            # Valida limites de tamanho
            if self.rules['chunk_size_limits'].enabled:
                chunk_size = len(chunk.text)
                
                if chunk_size < self.chunk_config.min_chunk_size:
                    issues.append(ValidationIssue(
                        rule_name='chunk_size_limits',
                        severity=ValidationSeverity.WARNING,
                        message=f'Chunk {i} muito pequeno: {chunk_size} caracteres',
                        details={
                            'chunk_index': i,
                            'chunk_size': chunk_size,
                            'min_size': self.chunk_config.min_chunk_size
                        },
                        location=f'Chunk {i}'
                    ))
                elif chunk_size > self.chunk_config.chunk_size * 1.5:  # 50% de tolerância
                    issues.append(ValidationIssue(
                        rule_name='chunk_size_limits',
                        severity=ValidationSeverity.WARNING,
                        message=f'Chunk {i} muito grande: {chunk_size} caracteres',
                        details={
                            'chunk_index': i,
                            'chunk_size': chunk_size,
                            'target_size': self.chunk_config.chunk_size
                        },
                        location=f'Chunk {i}'
                    ))
                else:
                    passed_checks += 1
            
            # Valida consistência de metadados
            if self.rules['metadata_consistency'].enabled:
                if not hasattr(chunk, 'metadata') or not chunk.metadata:
                    issues.append(ValidationIssue(
                        rule_name='metadata_consistency',
                        severity=ValidationSeverity.WARNING,
                        message=f'Chunk {i} sem metadados',
                        details={'chunk_index': i},
                        location=f'Chunk {i}'
                    ))
                else:
                    # Verifica campos obrigatórios nos metadados
                    required_fields = ['start_position', 'end_position']
                    missing_fields = []
                    
                    for field in required_fields:
                        if field not in chunk.metadata:
                            missing_fields.append(field)
                    
                    if missing_fields:
                        issues.append(ValidationIssue(
                            rule_name='metadata_consistency',
                            severity=ValidationSeverity.ERROR,
                            message=f'Chunk {i} com metadados incompletos: {missing_fields}',
                            details={'chunk_index': i, 'missing_fields': missing_fields},
                            location=f'Chunk {i}'
                        ))
                    else:
                        passed_checks += 1
            
            # Avalia coerência do conteúdo
            if self.rules['content_coherence'].enabled:
                # Verifica se o chunk termina no meio de uma palavra
                text = chunk.text.strip()
                if text and not text[-1] in '.!?;:\n' and len(text.split()) > 1:
                    last_word = text.split()[-1]
                    if not last_word.endswith(('.', '!', '?', ';', ':', ')', ']', '}')):
                        issues.append(ValidationIssue(
                            rule_name='content_coherence',
                            severity=ValidationSeverity.INFO,
                            message=f'Chunk {i} pode terminar no meio de uma frase',
                            details={'chunk_index': i, 'last_word': last_word},
                            location=f'Chunk {i}',
                            suggested_fix='Ajuste os limites do chunk para terminar em pontuação'
                        ))
                    else:
                        passed_checks += 1
                else:
                    passed_checks += 1
        
        # Valida sobreposições entre chunks consecutivos
        if self.rules['overlap_validation'].enabled and len(chunks) > 1:
            for i in range(len(chunks) - 1):
                current_chunk = chunks[i]
                next_chunk = chunks[i + 1]
                
                # Verifica se há sobreposição esperada
                if hasattr(current_chunk, 'metadata') and hasattr(next_chunk, 'metadata'):
                    if ('end_position' in current_chunk.metadata and 
                        'start_position' in next_chunk.metadata):
                        
                        current_end = current_chunk.metadata['end_position']
                        next_start = next_chunk.metadata['start_position']
                        
                        # Calcula sobreposição real
                        if next_start < current_end:
                            overlap = current_end - next_start
                            expected_overlap = self.chunk_config.chunk_overlap
                            
                            # Tolerância de 20%
                            tolerance = expected_overlap * 0.2
                            
                            if abs(overlap - expected_overlap) > tolerance:
                                issues.append(ValidationIssue(
                                    rule_name='overlap_validation',
                                    severity=ValidationSeverity.WARNING,
                                    message=f'Sobreposição inconsistente entre chunks {i} e {i+1}: {overlap} chars (esperado: {expected_overlap})',
                                    details={
                                        'chunk_1': i,
                                        'chunk_2': i + 1,
                                        'actual_overlap': overlap,
                                        'expected_overlap': expected_overlap
                                    },
                                    location=f'Chunks {i}-{i+1}'
                                ))
                            else:
                                passed_checks += 1
                        else:
                            # Sem sobreposição
                            if self.chunk_config.chunk_overlap > 0:
                                issues.append(ValidationIssue(
                                    rule_name='overlap_validation',
                                    severity=ValidationSeverity.WARNING,
                                    message=f'Sem sobreposição entre chunks {i} e {i+1}',
                                    details={'chunk_1': i, 'chunk_2': i + 1},
                                    location=f'Chunks {i}-{i+1}'
                                ))
                            else:
                                passed_checks += 1
        
        # Calcula score e resultado
        failed_checks = total_checks - passed_checks
        score = passed_checks / total_checks if total_checks > 0 else 0.0
        
        # Determina se é válido
        has_critical = any(issue.severity == ValidationSeverity.CRITICAL for issue in issues)
        has_errors = any(issue.severity == ValidationSeverity.ERROR for issue in issues)
        is_valid = not (has_critical or has_errors)
        
        processing_time = time.time() - start_time
        
        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            score=score,
            validation_level=ValidationLevel.STANDARD,
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            warnings=len([i for i in issues if i.severity == ValidationSeverity.WARNING]),
            errors=len([i for i in issues if i.severity == ValidationSeverity.ERROR]),
            processing_time=processing_time
        )

class MetadataValidator:
    """Validador para metadados extraídos."""
    
    def __init__(self):
        """Inicializa o validador de metadados."""
        self.rules = self._initialize_metadata_rules()
    
    def _initialize_metadata_rules(self) -> Dict[str, ValidationRule]:
        """Inicializa as regras de validação de metadados."""
        return {
            'required_fields': ValidationRule(
                name='required_fields',
                description='Verifica se os campos obrigatórios estão presentes',
                severity=ValidationSeverity.ERROR,
                custom_params={'required_fields': ['file_name', 'file_size', 'created_at']}
            ),
            'field_types': ValidationRule(
                name='field_types',
                description='Valida os tipos dos campos',
                severity=ValidationSeverity.ERROR
            ),
            'email_format': ValidationRule(
                name='email_format',
                description='Valida formato dos emails extraídos',
                severity=ValidationSeverity.WARNING
            ),
            'phone_format': ValidationRule(
                name='phone_format',
                description='Valida formato dos telefones extraídos',
                severity=ValidationSeverity.WARNING
            ),
            'url_format': ValidationRule(
                name='url_format',
                description='Valida formato das URLs extraídas',
                severity=ValidationSeverity.WARNING
            ),
            'completeness': ValidationRule(
                name='completeness',
                description='Avalia completude dos metadados',
                severity=ValidationSeverity.INFO
            )
        }
    
    def validate_metadata(self, metadata: Dict[str, Any]) -> ValidationResult:
        """Valida metadados extraídos."""
        start_time = time.time()
        
        issues = []
        total_checks = len(self.rules)
        passed_checks = 0
        
        # Verifica campos obrigatórios
        if self.rules['required_fields'].enabled:
            required_fields = self.rules['required_fields'].custom_params['required_fields']
            missing_fields = []
            
            for field in required_fields:
                if field not in metadata or metadata[field] is None:
                    missing_fields.append(field)
            
            if missing_fields:
                issues.append(ValidationIssue(
                    rule_name='required_fields',
                    severity=ValidationSeverity.ERROR,
                    message=f'Campos obrigatórios ausentes: {missing_fields}',
                    details={'missing_fields': missing_fields},
                    suggested_fix=f'Adicione os campos: {", ".join(missing_fields)}'
                ))
            else:
                passed_checks += 1
        
        # Valida tipos de campos
        if self.rules['field_types'].enabled:
            type_errors = []
            
            # Define tipos esperados
            expected_types = {
                'file_size': (int, float),
                'word_count': (int,),
                'char_count': (int,),
                'line_count': (int,),
                'created_at': (str,),
                'emails': (list,),
                'phones': (list,),
                'urls': (list,)
            }
            
            for field, expected_type in expected_types.items():
                if field in metadata and not isinstance(metadata[field], expected_type):
                    type_errors.append(f'{field}: esperado {expected_type}, recebido {type(metadata[field])}')
            
            if type_errors:
                issues.append(ValidationIssue(
                    rule_name='field_types',
                    severity=ValidationSeverity.ERROR,
                    message=f'Tipos de campos incorretos: {type_errors}',
                    details={'type_errors': type_errors}
                ))
            else:
                passed_checks += 1
        
        # Valida formato de emails
        if self.rules['email_format'].enabled:
            if 'emails' in metadata and isinstance(metadata['emails'], list):
                invalid_emails = []
                email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
                
                for email in metadata['emails']:
                    if not email_pattern.match(email):
                        invalid_emails.append(email)
                
                if invalid_emails:
                    issues.append(ValidationIssue(
                        rule_name='email_format',
                        severity=ValidationSeverity.WARNING,
                        message=f'Emails com formato inválido: {invalid_emails}',
                        details={'invalid_emails': invalid_emails}
                    ))
                else:
                    passed_checks += 1
            else:
                passed_checks += 1  # Campo opcional
        
        # Valida formato de telefones
        if self.rules['phone_format'].enabled:
            if 'phones' in metadata and isinstance(metadata['phones'], list):
                invalid_phones = []
                # Padrão brasileiro flexível
                phone_pattern = re.compile(r'^(\+55\s?)?(\(?\d{2}\)?\s?)?\d{4,5}[-\s]?\d{4}$')
                
                for phone in metadata['phones']:
                    if not phone_pattern.match(phone):
                        invalid_phones.append(phone)
                
                if invalid_phones:
                    issues.append(ValidationIssue(
                        rule_name='phone_format',
                        severity=ValidationSeverity.WARNING,
                        message=f'Telefones com formato inválido: {invalid_phones}',
                        details={'invalid_phones': invalid_phones}
                    ))
                else:
                    passed_checks += 1
            else:
                passed_checks += 1  # Campo opcional
        
        # Valida formato de URLs
        if self.rules['url_format'].enabled:
            if 'urls' in metadata and isinstance(metadata['urls'], list):
                invalid_urls = []
                url_pattern = re.compile(r'^https?://[^\s/$.?#].[^\s]*$', re.IGNORECASE)
                
                for url in metadata['urls']:
                    if not url_pattern.match(url):
                        invalid_urls.append(url)
                
                if invalid_urls:
                    issues.append(ValidationIssue(
                        rule_name='url_format',
                        severity=ValidationSeverity.WARNING,
                        message=f'URLs com formato inválido: {invalid_urls}',
                        details={'invalid_urls': invalid_urls}
                    ))
                else:
                    passed_checks += 1
            else:
                passed_checks += 1  # Campo opcional
        
        # Avalia completude dos metadados
        if self.rules['completeness'].enabled:
            # Lista de campos opcionais mas desejáveis
            optional_fields = ['auto_category', 'language', 'keywords', 'summary']
            present_optional = sum(1 for field in optional_fields if field in metadata and metadata[field])
            completeness_score = present_optional / len(optional_fields)
            
            if completeness_score < 0.5:
                issues.append(ValidationIssue(
                    rule_name='completeness',
                    severity=ValidationSeverity.INFO,
                    message=f'Metadados incompletos: {completeness_score:.1%} dos campos opcionais preenchidos',
                    details={'completeness_score': completeness_score, 'optional_fields': optional_fields}
                ))
            
            passed_checks += 1  # Não é falha, apenas informativo
        
        # Calcula score e resultado
        failed_checks = total_checks - passed_checks
        score = passed_checks / total_checks if total_checks > 0 else 0.0
        
        # Determina se é válido
        has_critical = any(issue.severity == ValidationSeverity.CRITICAL for issue in issues)
        has_errors = any(issue.severity == ValidationSeverity.ERROR for issue in issues)
        is_valid = not (has_critical or has_errors)
        
        processing_time = time.time() - start_time
        
        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            score=score,
            validation_level=ValidationLevel.STANDARD,
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            warnings=len([i for i in issues if i.severity == ValidationSeverity.WARNING]),
            errors=len([i for i in issues if i.severity == ValidationSeverity.ERROR]),
            processing_time=processing_time
        )

class ValidationManager:
    """Gerenciador principal do sistema de validação."""
    
    def __init__(self, validation_level: ValidationLevel = ValidationLevel.STANDARD):
        """Inicializa o gerenciador de validação."""
        self.validation_level = validation_level
        self.document_validator = DocumentValidator()
        self.content_validator = ContentValidator()
        self.chunk_validator = ChunkValidator()
        self.metadata_validator = MetadataValidator()
        
        # Histórico de validações
        self.validation_history: List[Dict[str, Any]] = []
    
    def validate_full_pipeline(
        self,
        file_path: Union[str, Path],
        content: str,
        chunks: List[Chunk],
        metadata: Dict[str, Any]
    ) -> Dict[str, ValidationResult]:
        """Executa validação completa do pipeline."""
        results = {}
        
        # Valida arquivo
        logger.info(f"Validando arquivo: {file_path}")
        results['document'] = self.document_validator.validate_file(file_path)
        
        # Valida conteúdo
        logger.info("Validando conteúdo extraído")
        results['content'] = self.content_validator.validate_content(content, metadata)
        
        # Valida chunks
        logger.info(f"Validando {len(chunks)} chunks")
        results['chunks'] = self.chunk_validator.validate_chunks(chunks, content)
        
        # Valida metadados
        logger.info("Validando metadados")
        results['metadata'] = self.metadata_validator.validate_metadata(metadata)
        
        # Salva no histórico
        self.validation_history.append({
            'timestamp': time.time(),
            'file_path': str(file_path),
            'validation_level': self.validation_level.value,
            'results': {k: self._serialize_validation_result(v) for k, v in results.items()}
        })
        
        return results
    
    def _serialize_validation_result(self, result: ValidationResult) -> Dict[str, Any]:
        """Serializa ValidationResult para JSON."""
        return {
            'is_valid': result.is_valid,
            'score': result.score,
            'validation_level': result.validation_level.value,
            'total_checks': result.total_checks,
            'passed_checks': result.passed_checks,
            'failed_checks': result.failed_checks,
            'warnings': result.warnings,
            'errors': result.errors,
            'processing_time': result.processing_time,
            'issues': [
                {
                    'rule_name': issue.rule_name,
                    'severity': issue.severity.value,
                    'message': issue.message,
                    'details': issue.details,
                    'location': issue.location,
                    'suggested_fix': issue.suggested_fix
                }
                for issue in result.issues
            ]
        }
    
    def get_overall_score(self, validation_results: Dict[str, ValidationResult]) -> float:
        """Calcula score geral da validação."""
        if not validation_results:
            return 0.0
        
        scores = [result.score for result in validation_results.values()]
        return sum(scores) / len(scores)
    
    def is_pipeline_valid(self, validation_results: Dict[str, ValidationResult]) -> bool:
        """Verifica se o pipeline inteiro é válido."""
        return all(result.is_valid for result in validation_results.values())
    
    def get_critical_issues(self, validation_results: Dict[str, ValidationResult]) -> List[ValidationIssue]:
        """Retorna todos os problemas críticos encontrados."""
        critical_issues = []
        for result in validation_results.values():
            critical_issues.extend(result.get_issues_by_severity(ValidationSeverity.CRITICAL))
        return critical_issues
    
    def get_validation_report(self, validation_results: Dict[str, ValidationResult]) -> Dict[str, Any]:
        """Gera relatório detalhado da validação."""
        overall_score = self.get_overall_score(validation_results)
        is_valid = self.is_pipeline_valid(validation_results)
        critical_issues = self.get_critical_issues(validation_results)
        
        total_issues = sum(len(result.issues) for result in validation_results.values())
        total_errors = sum(result.errors for result in validation_results.values())
        total_warnings = sum(result.warnings for result in validation_results.values())
        
        return {
            'overall_score': overall_score,
            'is_valid': is_valid,
            'validation_level': self.validation_level.value,
            'summary': {
                'total_issues': total_issues,
                'critical_issues': len(critical_issues),
                'errors': total_errors,
                'warnings': total_warnings
            },
            'component_scores': {
                component: result.score for component, result in validation_results.items()
            },
            'component_validity': {
                component: result.is_valid for component, result in validation_results.items()
            },
            'critical_issues': [issue.__dict__ for issue in critical_issues],
            'recommendations': self._generate_recommendations(validation_results)
        }
    
    def _generate_recommendations(self, validation_results: Dict[str, ValidationResult]) -> List[str]:
        """Gera recomendações baseadas nos resultados da validação."""
        recommendations = []
        
        # Analisa resultados e gera recomendações
        for component, result in validation_results.items():
            if not result.is_valid:
                if result.has_critical_issues():
                    recommendations.append(f"CRÍTICO: Resolva os problemas críticos em {component}")
                
                if result.has_errors():
                    recommendations.append(f"Corrija os erros encontrados em {component}")
            
            if result.score < 0.7:
                recommendations.append(f"Melhore a qualidade de {component} (score: {result.score:.2f})")
        
        # Recomendações gerais
        overall_score = self.get_overall_score(validation_results)
        if overall_score < 0.8:
            recommendations.append("Considere revisar o processo de ingestão para melhorar a qualidade geral")
        
        return recommendations
    
    def export_validation_history(self, file_path: Optional[str] = None) -> str:
        """Exporta histórico de validações para arquivo JSON."""
        import json
        from datetime import datetime
        
        if not file_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = f"validation_history_{timestamp}.json"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.validation_history, f, indent=2, ensure_ascii=False)
        
        return file_path 