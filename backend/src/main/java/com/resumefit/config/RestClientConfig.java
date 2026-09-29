package com.resumefit.config;

import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.http.converter.ByteArrayHttpMessageConverter;
import org.springframework.http.converter.StringHttpMessageConverter;
import org.springframework.http.converter.json.JacksonJsonHttpMessageConverter;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.json.JsonMapper;

@Configuration
public class RestClientConfig {

	@Bean
	RestClient aiServiceRestClient(AiServiceProperties properties, JsonMapper jsonMapper) {
		HttpClient httpClient = HttpClient.newBuilder()
				// The JDK client prefers HTTP/2. Uvicorn expects HTTP/1.1, and an
				// HTTP/2 attempt arrives with an empty JSON body.
				.version(HttpClient.Version.HTTP_1_1)
				.connectTimeout(Duration.ofSeconds(5))
				.build();
		JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
		requestFactory.setReadTimeout(properties.readTimeout());

		return RestClient.builder()
				.baseUrl(properties.normalizedUrl())
				.requestFactory(requestFactory)
				.messageConverters(List.of(
						new JacksonJsonHttpMessageConverter(jsonMapper),
						new ByteArrayHttpMessageConverter(),
						new StringHttpMessageConverter(StandardCharsets.UTF_8)))
				.build();
	}

}
