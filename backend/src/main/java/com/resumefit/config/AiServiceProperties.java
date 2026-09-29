package com.resumefit.config;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "ai.service")
public record AiServiceProperties(String url, Duration readTimeout) {

	public AiServiceProperties {
		if (url == null || url.isBlank()) {
			throw new IllegalArgumentException("ai.service.url must not be blank");
		}
		if (readTimeout == null || readTimeout.isNegative() || readTimeout.isZero()) {
			readTimeout = Duration.ofMinutes(10);
		}
	}

	public String normalizedUrl() {
		return url.replaceAll("/+$", "");
	}

}
