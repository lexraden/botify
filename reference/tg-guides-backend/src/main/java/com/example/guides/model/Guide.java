package com.example.guides.model;
import java.util.ArrayList;

import com.example.guides.constant.Language;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.ToString;
import javax.persistence.*;
import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.List;

@Table(name = "guide")
@Entity
@Data
@NoArgsConstructor
@AllArgsConstructor
@ToString(exclude = {"author", "chapters", "purchasedGuides"})
public class Guide implements Serializable {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private long id;

    private String name;

    @Column(name = "main_img")
    private String mainImg;

    private String description;

    @ManyToOne
    @JoinColumn(name = "person_id")
    private Person author;

    @OneToMany(mappedBy = "guide", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Chapter> chapters = new ArrayList<>();

    private int price;

    private int count;

    private int earnings;
    @Column(name = "weekly_earnings")
    private Integer weeklyEarnings; 
    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @OneToMany(mappedBy = "guide")
    private List<PurchasedGuides> purchasedGuides;

    @Enumerated(EnumType.STRING)
    private Language language;

    public String getTitle() {
        return name;
    }

    public void setTitle(String name) {
        this.name = name;
    }

}
