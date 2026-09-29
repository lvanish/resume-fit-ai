package com.resumefit.client;

import com.resumefit.dto.ErrorResponse;
import com.resumefit.dto.MatchRequest;
import com.resumefit.dto.MatchResponse;
import com.resumefit.exception.AiServiceException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import tools.jackson.databind.json.JsonMapper;

@Component
public class AiServiceClient {

	private static final Logger log = LoggerFactory.getLogger(AiServiceClient.class);

	private final RestClient restClient;
	private final JsonMapper jsonMapper;

	public AiServiceClient(RestClient aiServiceRestClient, JsonMapper jsonMapper) {
		this.restClient = aiServiceRestClient;
		this.jsonMapper = jsonMapper;
	}

	public MatchResponse analyze(MatchRequest request) {
		try {
			MatchResponse response = restClient.post()
					.uri("/api/v1/analyze")
					.contentType(MediaType.APPLICATION_JSON)
					.body(request)
					.retrieve()
					.onStatus(HttpStatusCode::isError, (httpRequest, httpResponse) -> {
						ErrorResponse error = readError(httpResponse);
						throw new AiServiceException(httpResponse.getStatusCode(), error.code(), error.message());
					})
					.body(MatchResponse.class);

			if (response == null) {
				throw new AiServiceException(
						HttpStatus.BAD_GATEWAY,
						"AI_SERVICE_ERROR",
						"The AI service returned an empty response.");
			}
			return response;
		}
		catch (AiServiceException exception) {
			throw exception;
		}
		catch (RestClientException exception) {
			log.warn("AI service request failed: {}", exception.getMessage());
			throw new AiServiceException(
					HttpStatus.BAD_GATEWAY,
					"AI_SERVICE_UNAVAILABLE",
					"The AI service could not be reached. Check that it is running and AI_SERVICE_URL is correct.");
		}
	}

	private ErrorResponse readError(org.springframework.http.client.ClientHttpResponse response) {
		try {
			byte[] bytes = response.getBody().readAllBytes();
			if (bytes.length == 0) {
				return new ErrorResponse("AI_SERVICE_ERROR", "The AI service returned an empty error response.");
			}
			ErrorResponse error = jsonMapper.readValue(bytes, ErrorResponse.class);
			String code = error.code() == null || error.code().isBlank() ? "AI_SERVICE_ERROR" : error.code();
			String message = error.message() == null || error.message().isBlank()
					? "The AI service returned an error."
					: error.message();
			return new ErrorResponse(code, message);
		}
		catch (Exception exception) {
			log.warn("Could not read AI service error response");
			return new ErrorResponse("AI_SERVICE_ERROR", "The AI service returned an unexpected error.");
		}
	}

}
