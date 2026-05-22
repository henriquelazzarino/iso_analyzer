package com.example.demo;

public class Order {
    private final int quantity;
    private final double price;

    public Order(int quantity, double price) {
        this.quantity = quantity;
        this.price = price;
    }

    public int getQuantity() { return quantity; }
    public double getPrice() { return price; }
}
