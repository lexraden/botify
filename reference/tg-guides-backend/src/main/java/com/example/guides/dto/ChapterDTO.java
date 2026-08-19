package com.example.guides.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "Объект для главы гайда")
public class ChapterDTO {

    @Schema(description = "Идентификатор главы")
    private Long id;

    @Schema(description = "Имя главы")
    private String name;

    @Schema(description = "Текстовое содержимое главы")
    private String text;

    @Schema(description = "Ссылка на изображение главы")
    private String img;

    @Schema(description = "Ссылка на видеоматериал главы")
    private String video;

}
