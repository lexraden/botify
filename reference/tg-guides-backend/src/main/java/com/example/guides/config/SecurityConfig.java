package com.example.guides.config;

import com.example.guides.security.JwtConfigurer;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.config.annotation.method.configuration.EnableGlobalMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.Arrays;

@Configuration
@EnableWebSecurity
@EnableGlobalMethodSecurity(prePostEnabled = true)
public class SecurityConfig extends WebSecurityConfigurerAdapter {

    private final JwtConfigurer jwtConfigurer;

    @Autowired
    public SecurityConfig(JwtConfigurer jwtConfigurer) {
        this.jwtConfigurer = jwtConfigurer;
    }

    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http
            .cors() // Enable CORS configuration
            .and()
            .csrf().disable() // Disable CSRF for stateless APIs
            .sessionManagement().sessionCreationPolicy(SessionCreationPolicy.STATELESS) // Use stateless session management
            .and()
            .authorizeRequests()
            .antMatchers(
                "/api/v1/auth/init",
                "/api/v1/user-profile/check-user/**",
                "/swagger-ui/**",
                "/v3/api-docs/**",
                "/v2/api-docs/**",
                "/api/v1/api-docs/**",
                "/swagger-resources/**",
                "/webjars/**"
            ).permitAll() // Allow access to specific endpoints without authentication
            .anyRequest().authenticated() // Require authentication for other requests
            .and()
            .apply(jwtConfigurer); // Apply JWT configuration
    }

    @Bean
    @Override
    public AuthenticationManager authenticationManagerBean() throws Exception {
        return super.authenticationManagerBean();
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        configuration.addAllowedOrigin("https://d2c5-178-216-216-59.ngrok-free.app"); 
        configuration.addAllowedOriginPattern("*"); 
        configuration.setAllowedMethods(Arrays.asList("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS")); 
        configuration.setAllowedHeaders(Arrays.asList("*"));
        configuration.setAllowCredentials(true);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }

}