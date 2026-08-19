package com.example.guides.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.math.BigDecimal;
import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "Объект пользователя")
public class PersonDTO {

    @Schema(description = "Идентификатор пользователя")
    private long id;

    @Schema(description = "Имя пользователя")
    private String firstName;

    @Schema(description = "Фамилия пользователя")
    private String lastName;

    @Schema(description = "Раздел \"О себе\"")
    private String description;

    @Schema(description = "Никнейм пользователя")
    private String username;

    @Schema(description = "Рефералки пользователя")
    private List<ReferralDTO> referrals;

    @Schema(description = "Личная реферальная ссылка пользователя")
    private String referralLink;

    @Schema(description = "Аватарка пользователя")
    private String imageUrl;

    @Schema(description = "Баланс пользователя")
    private BigDecimal balance;

    @Schema(description = "Название ссылки пользователя")
    private String linkName;

    @Schema(description = "URL пользователя")
    private String linkUrl;
}
