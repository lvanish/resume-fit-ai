package com.resumefit.exception;

import com.resumefit.dto.ErrorResponse;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {

	private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

	@ExceptionHandler(MethodArgumentNotValidException.class)
	public ResponseEntity<ErrorResponse> handleValidation(MethodArgumentNotValidException exception) {
		String message = exception.getBindingResult().getFieldErrors().stream()
				.map(error -> error.getDefaultMessage() == null ? "Invalid value" : error.getDefaultMessage())
				.collect(Collectors.joining("; "));
		if (message.isBlank()) {
			message = "Request validation failed.";
		}
		return ResponseEntity.badRequest().body(new ErrorResponse("VALIDATION_ERROR", message));
	}

	@ExceptionHandler(HttpMessageNotReadableException.class)
	public ResponseEntity<ErrorResponse> handleUnreadable(HttpMessageNotReadableException exception) {
		return ResponseEntity.badRequest().body(new ErrorResponse(
				"VALIDATION_ERROR",
				"Request body must be JSON with resume and jobDescription."));
	}

	@ExceptionHandler(AiServiceException.class)
	public ResponseEntity<ErrorResponse> handleAiService(AiServiceException exception) {
		log.warn("AI service call failed with status {} and code {}", exception.getStatus(), exception.getCode());
		return ResponseEntity.status(exception.getStatus())
				.body(new ErrorResponse(exception.getCode(), exception.getMessage()));
	}

	@ExceptionHandler(Exception.class)
	public ResponseEntity<ErrorResponse> handleUnexpected(Exception exception) {
		log.error("Unexpected error while handling a match request", exception);
		return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
				.body(new ErrorResponse("INTERNAL_ERROR", "An unexpected error occurred."));
	}

}
