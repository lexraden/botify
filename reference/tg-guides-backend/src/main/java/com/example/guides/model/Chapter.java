package com.example.guides.model;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import javax.persistence.*;
import java.io.Serializable;

@Table(name = "chapter")
@Entity
@Data
@NoArgsConstructor
@AllArgsConstructor
public class Chapter implements Serializable {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private long id;

    private String name;

    private String text;

    private String img;

    private String video;

    @ManyToOne
    @JoinColumn(name = "guide_id")
    private Guide guide;
}
