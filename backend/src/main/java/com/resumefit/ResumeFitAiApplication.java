package com.resumefit;

import com.resumefit.config.AiServiceProperties;
import com.resumefit.config.CorsProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties({AiServiceProperties.class, CorsProperties.class})
public class ResumeFitAiApplication {

	public static void main(String[] args) {
		SpringApplication.run(ResumeFitAiApplication.class, args);
	}

}
