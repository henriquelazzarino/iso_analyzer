package com.example.demo;

public class PriceCalculator {
    public double compute(Order o) {
        if (o.getQuantity() > 10) {
            return o.getPrice() * o.getQuantity() * 0.9;
        }
        return o.getPrice() * o.getQuantity();
    }
}
