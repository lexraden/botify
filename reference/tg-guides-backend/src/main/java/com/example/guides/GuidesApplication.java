package com.example.guides;

import org.springframework.boot.SpringApplication;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.web.servlet.config.annotation.EnableWebMvc;

@SpringBootApplication
@EnableWebMvc
public class GuidesApplication {

	public static void main(String[] args) {
		System.out.println("DB URL: " + System.getenv("DB_URL"));
        System.out.println("DB User: " + System.getenv("POSTGRES_USER"));
        System.out.println("DB Password: " + System.getenv("POSTGRES_PASSWORD"));
		SpringApplication.run(GuidesApplication.class, args);
	}

}
