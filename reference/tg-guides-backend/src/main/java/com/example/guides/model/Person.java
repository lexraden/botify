package com.example.guides.model;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.ToString;
import javax.persistence.*;
import java.io.Serializable;
import java.math.BigDecimal;
import java.util.List;

@Entity
@Table(name = "person")
@Data
@NoArgsConstructor
@AllArgsConstructor
@ToString(exclude = {"referrals", "referralOwners", "guides", "purchasedGuides"})
public class Person implements Serializable {

    @Id
    private long id;

    private String username;

    private String telegramChatId;



    @Column(name = "first_name")
    private String firstName;

    @Column(name = "last_name")
    private String lastName;

    private String description;

    private String role;

    private String password;

    @Column(name = "referral_link")
    private String referralLink;

    @OneToMany(mappedBy = "referral", fetch = FetchType.EAGER)
    private List<Referral> referrals;

    @OneToMany(mappedBy = "referralOwner")
    private List<Referral> referralOwners;

    @OneToMany(mappedBy = "author")
    private List<Guide> guides;

    @OneToMany(mappedBy = "person")
    private List<PurchasedGuides> purchasedGuides;

    @Column(name = "link_name")
    private String linkName;

    @Column(name = "link_url")
    private String linkUrl;
    // Поле баланса с значением по умолчанию 0.00
    @Column(name = "balance", precision = 19, scale = 2, columnDefinition = "DECIMAL(19, 2) DEFAULT '0.00'")
    private BigDecimal balance = BigDecimal.ZERO;  // Инициализация баланса как 0.00

    public long getTelegramChatId() {
        return id;
    }

    public void setTelegramChatId(String telegramChatId) {
        this.id = id;
    }
    public List<Referral> getReferredBy() {
        return referralOwners;
    }
    
}
