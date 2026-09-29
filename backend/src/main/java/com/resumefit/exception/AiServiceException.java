package com.resumefit.exception;

import org.springframework.http.HttpStatusCode;

public class AiServiceException extends RuntimeException {

	private final HttpStatusCode status;
	private final String code;

	public AiServiceException(HttpStatusCode status, String code, String message) {
		super(message);
		this.status = status;
		this.code = code;
	}

	public HttpStatusCode getStatus() {
		return status;
	}

	public String getCode() {
		return code;
	}

}
