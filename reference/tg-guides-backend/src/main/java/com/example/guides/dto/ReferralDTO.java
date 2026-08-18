package com.example.guides.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.util.HashSet;
import java.util.Set;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "Объект рефералки")
public class ReferralDTO {

    @Schema(description = "Приглашенное лицо")
    private PersonDTO referral;

    // Множество для предотвращения зацикливания
    private Set<Long> visitedReferrals = new HashSet<>();

    public ReferralDTO(PersonDTO referral) {
        this.referral = referral;
        this.visitedReferrals = new HashSet<>();
    }
}
