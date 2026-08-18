package com.example.guides.constant;

import lombok.Getter;

@Getter
public enum Language {

    RU("RU"),
    ENG("ENG");

    private final String lang;

    Language(String lang) {
        this.lang = lang;
    }
}
