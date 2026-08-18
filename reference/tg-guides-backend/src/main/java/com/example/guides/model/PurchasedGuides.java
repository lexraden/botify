package com.example.guides.model;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import javax.persistence.*;
import java.time.LocalDateTime;

@Table(name = "purchased_guides")
@Entity
@Data
@NoArgsConstructor
@AllArgsConstructor
public class PurchasedGuides {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private long id;

    @ManyToOne
    @JoinColumn(name = "person_id")
    private Person person;

    @ManyToOne
    @JoinColumn(name = "guide_id")
    private Guide guide;

    @Column(name = "purchase_date")
    private LocalDateTime purchaseDate;

    @Column(name = "purchase_price")
    private Integer purchasePrice;

    public PurchasedGuides(Person person, Guide guide) {
        this.person = person;
        this.guide = guide;
        this.purchaseDate = LocalDateTime.now(); 
        this.purchasePrice = guide.getPrice();  
    }
}
