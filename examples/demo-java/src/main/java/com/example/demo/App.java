package com.example.demo;

import java.util.Arrays;
import java.util.List;

public class App {
    public static void main(String[] args) {
        OrderService service = new OrderService(new PriceCalculator(), new Logger());
        List<Order> orders = Arrays.asList(new Order(2, 10.0), new Order(15, 5.0));
        System.out.println("Total: " + service.total(orders));
    }
}
