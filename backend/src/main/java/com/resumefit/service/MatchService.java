package com.resumefit.service;

import com.resumefit.client.AiServiceClient;
import com.resumefit.dto.MatchRequest;
import com.resumefit.dto.MatchResponse;
import org.springframework.stereotype.Service;

@Service
public class MatchService {

	private final AiServiceClient aiServiceClient;

	public MatchService(AiServiceClient aiServiceClient) {
		this.aiServiceClient = aiServiceClient;
	}

	public MatchResponse analyze(MatchRequest request) {
		return aiServiceClient.analyze(request);
	}

}
