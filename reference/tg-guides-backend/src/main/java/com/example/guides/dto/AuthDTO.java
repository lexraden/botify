package com.example.guides.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(name = "Объект авторизации")
public class AuthDTO {

    @Schema(description = "Идентификатор пользователя")
    private long id;

    @Schema(description = "Никнейм пользователя")
    private String username;

    @Schema(description = "Имя пользователя")
    private String firstName;

    @Schema(description = "Фамилия пользователя")
    private String lastName;

}
