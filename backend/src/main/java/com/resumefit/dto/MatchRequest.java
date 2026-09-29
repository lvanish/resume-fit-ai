package com.resumefit.dto;

import jakarta.validation.constraints.NotBlank;

public record MatchRequest(
		@NotBlank(message = "resume must not be blank") String resume,
		@NotBlank(message = "jobDescription must not be blank") String jobDescription
) {
}
